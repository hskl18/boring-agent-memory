#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""Draw the README's abstention chart from the committed Benchmark v1 result.

Run `uv run scripts/plot_abstention.py` to rewrite docs/media/abstention.png.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "benchmarks/v1/results/abstention-python-3.12-macos-arm64.json"
OUTPUT = ROOT / "docs/media/abstention.png"
METRICS = (
    ("positive_recall_at_3", "Found the answer\n(Recall@3, 100 queries)"),
    ("easy_no_answer_precision", "Returned nothing\n(20 easy no-answer)"),
    ("adversarial_no_answer_precision", "Returned nothing\n(20 adversarial no-answer)"),
)
MODES = (("default", "Default", "#4c78a8"), ("strict", "--strict", "#f58518"))

plt.rcParams.update(
    {"font.size": 11, "axes.spines.top": False, "axes.spines.right": False}
)
result = json.loads(RESULT.read_text())
figure, axis = plt.subplots(figsize=(8, 3.2), facecolor="white")
for index, (mode, label, color) in enumerate(MODES):
    offsets = [position + (index - 0.5) * 0.36 for position in range(len(METRICS))]
    bars = axis.bar(
        offsets,
        [100 * result[mode][key] for key, _ in METRICS],
        width=0.36,
        label=label,
        color=color,
    )
    axis.bar_label(bars, fmt="%.0f%%")
axis.set_xticks(range(len(METRICS)), [name for _, name in METRICS])
axis.set_ylim(0, 112)
axis.set_yticks([0, 50, 100], ["0%", "50%", "100%"])
axis.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncols=2)
figure.tight_layout()
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
figure.savefig(OUTPUT, dpi=160, metadata={"Software": None})
