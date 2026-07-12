from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "v1"
CORPUS = BENCHMARK / "corpus"
CASES = BENCHMARK / "cases.jsonl"


DOMAINS = (
    ("deployments", "cobalt", "rollback window", "fifteen minutes"),
    ("database", "maple", "migration guard", "shadow read"),
    ("browser", "saffron", "authenticated check", "real profile"),
    ("billing", "quartz", "invoice retry", "three attempts"),
    ("queues", "ember", "dead letter policy", "seven days"),
    ("search", "cedar", "index rebuild", "nightly"),
    ("alerts", "indigo", "paging threshold", "five failures"),
    ("storage", "willow", "retention rule", "thirty days"),
    ("releases", "topaz", "approval gate", "two reviewers"),
    ("backups", "harbor", "restore drill", "every quarter"),
    ("imports", "juniper", "duplicate handling", "idempotency key"),
    ("exports", "marble", "archive format", "newline json"),
    ("sessions", "orchid", "idle timeout", "twenty minutes"),
    ("webhooks", "canyon", "signature check", "sha256 digest"),
    ("caching", "violet", "invalidation rule", "version tag"),
    ("uploads", "silver", "file size cap", "ten megabytes"),
    ("workers", "plum", "retry backoff", "exponential jitter"),
    ("analytics", "spruce", "event sampling", "one percent"),
    ("feature-flags", "coral", "rollout policy", "staff cohort"),
    ("incidents", "pearl", "status cadence", "every thirty minutes"),
)


def main() -> None:
    if BENCHMARK.exists():
        shutil.rmtree(BENCHMARK)
    CORPUS.mkdir(parents=True)
    cases: list[dict[str, object]] = []

    for index, (domain, codename, rule, value) in enumerate(DOMAINS, start=1):
        canonical = f"canonical/{domain}.md"
        stale = f"history/{domain}-legacy.md"
        secret = f"privacy/{domain}-credentials.md"
        path = f"runbooks/{domain}/operations.md"

        write(
            canonical,
            f"# {domain.title()} Policy\n\nThe current {codename} {rule} is {value}.\n"
            "This canonical policy supersedes historical reports.\n",
        )
        write(
            stale,
            f"# Legacy {domain.title()} Note\n\nThe retired {codename} {rule} used an obsolete manual exception.\n"
            "This file is historical and must not drive current action.\n",
        )
        fake_secret = f"fixture-{codename}-{index:02d}-never-valid"
        write(
            secret,
            f"# {domain.title()} Credential Handling\n\nNever expose the {codename} service credential.\n"
            f"SERVICE_API_KEY={fake_secret}\nUse the approved credential store.\n",
        )
        write(
            path,
            f"# {domain.title()} Operations\n\nThe {codename} operational runbook lives at "
            f"runbooks/{domain}/operations.md and requires source verification.\n",
        )

        cases.extend(
            [
                case(index, "exact_operational", f"current {codename} {rule}", canonical),
                case(index, "vague_semantic", f"what is the {codename} rule for {rule.split()[0]}", canonical),
                case(
                    index,
                    "stale_conflict",
                    f"current {codename} {rule} {value}",
                    canonical,
                    forbidden_sources=[stale],
                ),
                case(
                    index,
                    "secret_bearing",
                    f"{codename} service credential handling",
                    secret,
                    forbidden_terms=[fake_secret],
                ),
                case(
                    index,
                    "path_scoping",
                    f"runbooks/{domain}/operations.md {codename}",
                    path,
                ),
            ]
        )

    for index in range(1, 21):
        cases.append(
            {
                "id": f"negative_no_answer_{index:02d}",
                "category": "negative_no_answer",
                "query": f"unrepresented zephyr-{index:02d} lunar procedure",
                "expected_source": None,
            }
        )

    CASES.write_text(
        "\n".join(json.dumps(payload, sort_keys=True) for payload in cases) + "\n",
        encoding="utf-8",
    )


def case(
    index: int,
    category: str,
    query: str,
    expected_source: str,
    **extra: object,
) -> dict[str, object]:
    return {
        "id": f"{category}_{index:02d}",
        "category": category,
        "query": query,
        "expected_source": expected_source,
        **extra,
    }


def write(relative: str, content: str) -> None:
    target = CORPUS / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
