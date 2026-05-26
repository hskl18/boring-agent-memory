# Future Vector Layer

BM25 stays the default retrieval path. A vector layer should be added only when lexical search repeatedly misses real workflow questions.

Recommended shape:

1. Run BM25 first.
2. Use local embeddings only when BM25 returns too little or low-quality recall.
3. Rerank against source-grounded snippets.
4. Keep source paths and canonical verification mandatory.

Non-goals:

- hosted embedding API as a default
- vector memory as truth
- automatic ingestion of raw chat or tool output
