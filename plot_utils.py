"""
plot_utils.py — shared plotting helpers used across scripts.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


@contextmanager
def figure(figsize: tuple[float, float] = (10, 6)):
    """
    Context manager that creates a (fig, ax) pair and guarantees
    plt.close() is called on exit, even if plotting raises an exception.

    Usage
    -----
    with figure(figsize=(10, 6)) as (fig, ax):
        sns.lineplot(..., ax=ax)
        fig.savefig("out.png")
    """
    fig, ax = plt.subplots(figsize=figsize)
    try:
        yield fig, ax
    finally:
        plt.close(fig)


def save_fig(fig: plt.Figure, path: str | Path, dpi: int = 300) -> None:
    """Save a figure and close it. Creates parent directories if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def annotate_line_ends(
    ax: plt.Axes,
    labels: list[str],
    palette: dict[str, tuple],
    x_offset: int = 5,
    fontsize: int = 7,
) -> None:
    """
    Annotate the right-hand end of each data line on `ax` with its label.

    Expects lines in the same order as `labels`. Lines with fewer than
    3 points (e.g. Seaborn internals) are ignored.
    """
    data_lines = [l for l in ax.get_lines() if len(l.get_xdata()) > 2]
    for line, label in zip(data_lines, labels):
        xdata = np.asarray(line.get_xdata(), dtype=float)
        ydata = np.asarray(line.get_ydata(), dtype=float)
        valid = ~(np.isnan(xdata) | np.isnan(ydata))
        if valid.any():
            ax.annotate(
                label,
                xy=(xdata[valid][-1], ydata[valid][-1]),
                xytext=(x_offset, 0),
                textcoords="offset points",
                va="center",
                fontsize=fontsize,
                color=palette.get(label, line.get_color()),
                annotation_clip=False,
            )
