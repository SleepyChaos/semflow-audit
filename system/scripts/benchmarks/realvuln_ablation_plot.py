"""Render six-arm scientific figures from verified aggregate receipts."""

import argparse
import csv
from pathlib import Path


def plot(output):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    rows = list(csv.DictReader((output / "ablation-summary.csv").open()))
    if len(rows) != 6 or any(not row.get("f3") for row in rows):
        raise RuntimeError("All six full-project metrics are required")
    groups = [r["group"] for r in rows]
    colors = ["#648597", "#4f8584", "#40707c", "#ba8d5b", "#ac765c", "#8b665e"]
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.dpi": 180,
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    x = np.arange(6)
    width = 0.27
    for offset, field, color in [
        (-width, "precision", "#4f8584"),
        (0, "recall", "#648597"),
        (width, "f3", "#ac765c"),
    ]:
        values = [100 * float(r[field]) for r in rows]
        bars = axes[0].bar(
            x + offset, values, width, label=field.capitalize(), color=color
        )
        axes[0].bar_label(bars, fmt="%.1f", fontsize=6, padding=2)
    axes[0].set(
        xticks=x,
        xticklabels=groups,
        ylim=(0, 100),
        ylabel="Score (0–100)",
        title="Precision, recall and recall-weighted F3",
    )
    axes[0].legend(frameon=False, loc="upper left", ncol=3, fontsize=8)
    for row, color in zip(rows, colors, strict=True):
        axes[1].scatter(int(row["fp"]), int(row["tp"]), color=color, s=70)
        axes[1].annotate(
            row["group"],
            (int(row["fp"]), int(row["tp"])),
            xytext=(6, 7),
            textcoords="offset points",
        )
    axes[1].set(
        xlabel="Unmatched outputs (FP)",
        ylabel="Matched vulnerabilities (TP)",
        title="Detection gain versus unmatched output volume",
        xlim=(0, max(int(r["fp"]) for r in rows) * 1.1),
        ylim=(0, max(int(r["tp"]) for r in rows) * 1.15),
    )
    for ax in axes:
        ax.grid(axis="y", alpha=0.15)
        ax.set_axisbelow(True)
    fig.suptitle(
        "RealVuln ablation: 26 projects / 676 positives / single paired run",
        fontsize=12,
    )
    for suffix in ("png", "svg", "pdf"):
        fig.savefig(output / f"ablation-comparison.{suffix}")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plot(args.output)


if __name__ == "__main__":
    main()
