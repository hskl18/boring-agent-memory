from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol, Sequence, cast

from .privacy import redact_secrets
from .query import QueryResult
from .schema import connect, init_db


class EmbeddingAdapter(Protocol):
    model_id: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedAdapter:
    """Optional FastEmbed adapter with a strict no-download default."""

    def __init__(
        self,
        model_name: str,
        model_path: Path | str | None = None,
        allow_download: bool = False,
        cache_dir: Path | str | None = None,
    ) -> None:
        if model_path is None and not allow_download:
            raise ValueError(
                "a local embedding model path is required unless allow_download=True"
            )
        resolved_model_path = Path(model_path).expanduser().resolve() if model_path else None
        if resolved_model_path is not None and not resolved_model_path.exists():
            raise FileNotFoundError(f"embedding model path does not exist: {resolved_model_path}")
        try:
            from fastembed import TextEmbedding  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "optional embeddings require: pip install 'boring-agent-memory[embeddings]'"
            ) from exc

        resolved_cache_dir = (
            Path(cache_dir).expanduser().resolve().as_posix()
            if cache_dir is not None
            else None
        )
        self._model = TextEmbedding(
            model_name=model_name,
            cache_dir=resolved_cache_dir,
            local_files_only=not allow_download,
            specific_model_path=(
                resolved_model_path.as_posix()
                if resolved_model_path is not None
                else None
            ),
        )
        self.model_id = model_name
        self.allow_download = allow_download
        self.model_path = resolved_model_path

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        redacted_texts = [redact_secrets(text)[0] for text in texts]
        return [_vector(values) for values in self._model.embed(redacted_texts)]

    def embed_query(self, text: str) -> list[float]:
        text = redact_secrets(text)[0]
        query_embed = getattr(self._model, "query_embed", None)
        values = next(iter(query_embed(text) if query_embed else self._model.embed([text])))
        return _vector(values)


@dataclass(frozen=True)
class EmbeddingDocument:
    result: QueryResult
    text: str


@dataclass(frozen=True)
class DenseIndex:
    adapter: EmbeddingAdapter
    documents: tuple[EmbeddingDocument, ...]
    vectors: tuple[tuple[float, ...], ...]

    @classmethod
    def build(
        cls,
        adapter: EmbeddingAdapter,
        documents: Sequence[EmbeddingDocument],
    ) -> DenseIndex:
        vectors = adapter.embed_documents(
            [redact_secrets(document.text)[0] for document in documents]
        )
        if len(vectors) != len(documents):
            raise ValueError("embedding adapter returned the wrong number of vectors")
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) > 1 or dimensions == {0}:
            raise ValueError("embedding adapter returned inconsistent vector dimensions")
        return cls(
            adapter=adapter,
            documents=tuple(documents),
            vectors=tuple(tuple(vector) for vector in vectors),
        )

    def query(self, text: str, limit: int = 5) -> list[QueryResult]:
        query_vector = self.adapter.embed_query(redact_secrets(text)[0])
        if self.vectors and len(query_vector) != len(self.vectors[0]):
            raise ValueError("query vector dimension does not match the dense index")
        scored = [
            (cosine_similarity(query_vector, vector), document.result)
            for document, vector in zip(self.documents, self.vectors)
        ]
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        seen_documents: set[str] = set()
        results: list[QueryResult] = []
        for score, result in scored:
            if result.id in seen_documents:
                continue
            seen_documents.add(result.id)
            results.append(replace(result, score=-score, strategy="dense"))
            if len(results) >= limit:
                break
        return results


def load_embedding_documents(
    db_path: Path | str,
    source_type: str | None = None,
    workspace: Path | str | None = None,
) -> list[EmbeddingDocument]:
    conn = connect(db_path)
    init_db(conn)
    try:
        filters: list[str] = []
        params: list[object] = []
        if source_type:
            filters.append("d.source_type = ?")
            params.append(source_type)
        if workspace:
            filters.append("d.workspace = ?")
            params.append(Path(workspace).expanduser().resolve().as_posix())
        where = "WHERE " + " AND ".join(filters) if filters else ""
        rows = conn.execute(
            f"""
            SELECT
              d.id, c.id AS chunk_id, d.source_type, d.source_path,
              d.workspace, d.title, c.heading, c.start_line, c.end_line,
              c.content
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            {where}
            ORDER BY d.source_path, c.ordinal
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    documents: list[EmbeddingDocument] = []
    for row in rows:
        location = f"L{row['start_line']}-L{row['end_line']}"
        citation = f"{row['source_path']}:{location}"
        if row["heading"]:
            citation = f"{row['source_path']}#{row['heading']}:{location}"
        result = QueryResult(
            id=row["id"],
            chunk_id=row["chunk_id"],
            source_type=row["source_type"],
            source_path=row["source_path"],
            workspace=row["workspace"],
            title=row["title"],
            heading=row["heading"],
            start_line=int(row["start_line"]),
            end_line=int(row["end_line"]),
            citation=citation,
            score=0.0,
            snippet=row["content"],
            strategy="dense",
        )
        embedding_fields = (
            redact_secrets(value)[0]
            for value in (row["title"], row["heading"], row["content"])
            if value
        )
        text = "\n".join(embedding_fields)
        documents.append(EmbeddingDocument(result=result, text=text))
    return documents


def reciprocal_rank_fusion(
    lexical: Sequence[QueryResult],
    dense: Sequence[QueryResult],
    limit: int,
    lexical_weight: float = 0.6,
    dense_weight: float = 0.4,
    rrf_k: int = 60,
) -> list[QueryResult]:
    scores: dict[str, float] = {}
    results: dict[str, QueryResult] = {}
    tie_breaks: dict[str, tuple[int, int, str]] = {}
    missing_rank = 10**9
    lexical_ranks = {result.chunk_id: rank for rank, result in enumerate(lexical, start=1)}
    dense_ranks = {result.chunk_id: rank for rank, result in enumerate(dense, start=1)}
    for result in [*lexical, *dense]:
        results.setdefault(result.chunk_id, result)
    for chunk_id, result in results.items():
        lexical_rank = lexical_ranks.get(chunk_id)
        dense_rank = dense_ranks.get(chunk_id)
        score = 0.0
        if lexical_rank is not None:
            score += lexical_weight / (rrf_k + lexical_rank)
        if dense_rank is not None:
            score += dense_weight / (rrf_k + dense_rank)
        scores[chunk_id] = score
        tie_breaks[chunk_id] = (
            lexical_rank or missing_rank,
            dense_rank or missing_rank,
            chunk_id,
        )
    ordered = sorted(results, key=lambda key: (-scores[key], tie_breaks[key]))
    seen_documents: set[str] = set()
    fused: list[QueryResult] = []
    for chunk_id in ordered:
        result = results[chunk_id]
        if result.id in seen_documents:
            continue
        seen_documents.add(result.id)
        fused.append(replace(result, score=-scores[chunk_id], strategy="hybrid_rrf"))
        if len(fused) >= limit:
            break
    return fused


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vector dimensions do not match")
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _vector(values: object) -> list[float]:
    if hasattr(values, "tolist"):
        values = values.tolist()
    if not isinstance(values, Iterable):
        raise TypeError("embedding adapter returned a non-iterable vector")
    return [float(value) for value in cast(Iterable[Any], values)]
