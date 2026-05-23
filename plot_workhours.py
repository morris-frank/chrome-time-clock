#!/usr/bin/env python3
"""Work-hours timelines + histograms in dark Soilytix style."""

import argparse
import csv
import statistics
from datetime import date, datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.gridspec import GridSpec

# ── Soilytix dark palette ─────────────────────────────────────────────────────

C = {
    "fig_bg":    "#111614",
    "axes_bg":   "#161e1b",
    "text":      "#fdfefc",
    "muted":     "#837e75",
    "dimmed":    "#7d7a75",
    "border":    "#2a3a34",
    "grid":      "#1d2b26",
    "primary":   "#00ff87",   # mint  — weekly line
    "secondary": "#86eb22",   # lime  — daily bars / histograms
    "red":       "#b14117",
    "blue":      "#1a4f8a",
    "cyan":      "#0f7a65",
    "weekend":   "#0c1410",   # darker strip for Sat/Sun
}

STAT_COLORS = {
    "min":    C["blue"],
    "max":    C["red"],
    "mean":   C["cyan"],
    "median": C["muted"],
}

# ── Load ──────────────────────────────────────────────────────────────────────

def load_daily(path: Path, date_from: date | None, date_to: date | None) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = datetime.strptime(row["date"], "%Y-%m-%d").date()
            if date_from and d < date_from:
                continue
            if date_to and d > date_to:
                continue
            rows.append({
                "date":         d,
                "weekday":      d.weekday(),          # 0=Mon … 6=Sun
                "iso_week":     d.isocalendar()[:2],  # (year, week)
                "active_hours": float(row["active_block_hours"]),
            })
    return rows

# ── Aggregation ───────────────────────────────────────────────────────────────

def _to_dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def daily_series(rows: list[dict], weekdays_only: bool) -> tuple[list[datetime], list[float]]:
    out = [(r["date"], r["active_hours"]) for r in rows
           if not weekdays_only or r["weekday"] < 5]
    if not out:
        return [], []
    dates, hours = zip(*out)
    return [_to_dt(d) for d in dates], list(hours)


def _iso_week_wednesday(year: int, week: int) -> date:
    jan4 = date(year, 1, 4)
    monday_w1 = jan4 - timedelta(days=jan4.weekday())
    return monday_w1 + timedelta(weeks=week - 1, days=2)


def weekly_series(rows: list[dict], weekdays_only: bool) -> tuple[list[datetime], list[float]]:
    by_week: dict[tuple, float] = {}
    for r in rows:
        if weekdays_only and r["weekday"] >= 5:
            continue
        by_week[r["iso_week"]] = by_week.get(r["iso_week"], 0.0) + r["active_hours"]
    items = sorted(by_week.items())
    if not items:
        return [], []
    dates = [_to_dt(_iso_week_wednesday(y, w)) for (y, w), _ in items]
    hours = [v for _, v in items]
    return dates, hours


def hist_values(rows: list[dict], weekdays_only: bool, is_weekly: bool) -> list[float]:
    _, hours = (weekly_series if is_weekly else daily_series)(rows, weekdays_only)
    return hours


def date_range_all(rows: list[dict]) -> list[datetime]:
    """Every calendar day from first to last row date."""
    first, last = rows[0]["date"], rows[-1]["date"]
    out, d = [], first
    while d <= last:
        out.append(_to_dt(d))
        d += timedelta(days=1)
    return out

# ── Theme helpers ─────────────────────────────────────────────────────────────

def apply_style() -> None:
    plt.rcParams.update({
        "font.family":      "sans-serif",
        "font.sans-serif":  ["Inter", "Aptos", "Helvetica Neue", "Arial"],
        "figure.facecolor": C["fig_bg"],
        "axes.facecolor":   C["axes_bg"],
        "text.color":       C["text"],
        "axes.labelcolor":  C["muted"],
        "xtick.color":      C["muted"],
        "ytick.color":      C["muted"],
        "axes.edgecolor":   C["border"],
        "grid.color":       C["grid"],
        "grid.linewidth":   0.5,
        "legend.facecolor": C["axes_bg"],
        "legend.edgecolor": C["border"],
        "legend.labelcolor": C["text"],
    })


def dress_axes(ax: plt.Axes, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_facecolor(C["axes_bg"])
    for spine in ax.spines.values():
        spine.set_edgecolor(C["border"])
    ax.tick_params(colors=C["muted"], labelsize=8)
    ax.set_xlabel(xlabel, fontsize=8.5, color=C["muted"])
    ax.set_ylabel(ylabel, fontsize=8.5, color=C["muted"])
    ax.set_axisbelow(True)
    ax.grid(axis="y", zorder=1)


def shade_weekends(ax: plt.Axes, all_dts: list[datetime]) -> None:
    for dt in all_dts:
        if dt.weekday() >= 5:           # 5=Sat, 6=Sun
            ax.axvspan(dt - timedelta(hours=12), dt + timedelta(hours=12),
                       color=C["weekend"], alpha=1.0, zorder=0)


def stat_box(ax: plt.Axes, values: list[float]) -> None:
    if not values:
        return
    stats = {
        "min":    min(values),
        "max":    max(values),
        "mean":   statistics.mean(values),
        "median": statistics.median(values),
    }
    for label, val in stats.items():
        ax.axvline(val, color=STAT_COLORS[label], linewidth=1.3,
                   linestyle="--", alpha=0.9, zorder=4)
    box_text = "\n".join(f"{k:<7}{v:.2f} h" for k, v in stats.items())
    ax.text(
        0.97, 0.97, box_text,
        transform=ax.transAxes, ha="right", va="top",
        fontsize=8, fontfamily="monospace", color=C["text"],
        bbox=dict(boxstyle="round,pad=0.4", facecolor=C["fig_bg"],
                  edgecolor=C["primary"], linewidth=0.9, alpha=0.95),
        zorder=5,
    )

# ── Timeline ──────────────────────────────────────────────────────────────────

def plot_timeline(ax: plt.Axes, rows: list[dict]) -> None:
    all_dts = date_range_all(rows)
    shade_weekends(ax, all_dts)

    daily_dates, daily_hours = daily_series(rows, weekdays_only=False)
    weekly_dates, weekly_hours = weekly_series(rows, weekdays_only=False)

    # Daily bars (lime, left axis)
    ax.bar(daily_dates, daily_hours,
           color=C["secondary"], alpha=0.78, width=0.72, zorder=2,
           label="Daily active h")
    dress_axes(ax, ylabel="Active hours (day)")

    # Weekly line (mint, right axis)
    ax_w = ax.twinx()
    ax_w.plot(weekly_dates, weekly_hours,
              color=C["primary"], linewidth=2.0, marker="o", markersize=5,
              markerfacecolor=C["primary"], markeredgecolor=C["fig_bg"],
              markeredgewidth=1.4, zorder=3, label="Weekly total h")
    ax_w.tick_params(colors=C["primary"], labelsize=8)
    ax_w.set_ylabel("Active hours (week)", fontsize=8.5, color=C["primary"])
    ax_w.spines["right"].set_edgecolor(C["primary"])
    for s in ("top", "left", "bottom"):
        ax_w.spines[s].set_visible(False)
    ax_w.grid(False)
    ax_w.yaxis.set_major_locator(ticker.MaxNLocator(integer=False, nbins=5))

    # x-axis date formatting
    span_days = (rows[-1]["date"] - rows[0]["date"]).days
    if span_days <= 60:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    elif span_days <= 180:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=35, ha="right", fontsize=8)

    # x range with a half-day margin
    ax.set_xlim(all_dts[0] - timedelta(hours=12), all_dts[-1] + timedelta(hours=12))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=False, nbins=6))

    # Legend combining both axes
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax_w.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8.5,
              facecolor=C["axes_bg"], edgecolor=C["border"])

    ax.set_title(
        "Active hours — daily bars  +  weekly total  (weekends shaded)",
        fontsize=10.5, color=C["text"], pad=8, fontweight="bold",
    )

# ── Histogram ─────────────────────────────────────────────────────────────────

HIST_PANELS = [
    ("Daily — all days",       False, False, "Active hours (day)"),
    ("Daily — weekdays only",  True,  False, "Active hours (day)"),
    ("Weekly — all days",      False, True,  "Active hours (week)"),
    ("Weekly — weekdays only", True,  True,  "Active hours (week)"),
]


def plot_histogram(ax: plt.Axes, values: list[float],
                   title: str, xlabel: str, bins: int) -> None:
    if not values:
        ax.text(0.5, 0.5, "no data", ha="center", va="center",
                transform=ax.transAxes, color=C["muted"])
        ax.set_title(title, fontsize=9.5, color=C["text"], pad=6, fontweight="bold")
        return

    n_bins = min(bins, max(5, len(values) // 2))
    ax.hist(values, bins=n_bins,
            color=C["secondary"], edgecolor=C["axes_bg"],
            linewidth=0.6, alpha=0.88, zorder=2)
    dress_axes(ax, xlabel=xlabel, ylabel="Count")
    ax.set_title(title, fontsize=9.5, color=C["text"], pad=6, fontweight="bold")
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.text(0.03, 0.97, f"n={len(values)}",
            transform=ax.transAxes, ha="left", va="top",
            fontsize=8, color=C["muted"])
    stat_box(ax, values)

# ── Figure assembly ───────────────────────────────────────────────────────────

def build_figure(rows: list[dict], date_from: date | None,
                 bins: int, out_stem: str) -> None:
    apply_style()

    fig = plt.figure(figsize=(16, 16))
    gs = GridSpec(
        3, 2, figure=fig,
        height_ratios=[1.8, 1.4, 1.4],
        hspace=0.55, wspace=0.32,
        left=0.07, right=0.94, top=0.94, bottom=0.05,
    )

    subtitle = f"after {date_from}" if date_from else "all available history"
    fig.suptitle(
        f"Soilytix  ·  Work Hours  ·  {subtitle}",
        fontsize=14, fontweight="bold", color=C["text"], y=0.975,
    )

    # Timeline (full width)
    ax_tl = fig.add_subplot(gs[0, :])
    plot_timeline(ax_tl, rows)

    # 2 × 2 histograms
    positions = [(1, 0), (1, 1), (2, 0), (2, 1)]
    for (r, c), (title, wd_only, is_weekly, xlabel) in zip(positions, HIST_PANELS):
        ax = fig.add_subplot(gs[r, c])
        plot_histogram(ax, hist_values(rows, wd_only, is_weekly), title, xlabel, bins)

    # Export
    for ext in ("png", "pdf"):
        out = f"{out_stem}.{ext}"
        fig.savefig(out, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        print(f"Saved: {out}")

    plt.show()

# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="Work-hour timelines and histograms in dark Soilytix style."
    )
    p.add_argument("csv",              help="daily summary CSV")
    p.add_argument("--from", dest="date_from", default="2026-02-22")
    p.add_argument("--to",   dest="date_to",   default=None)
    p.add_argument("--bins", type=int,          default=15)
    p.add_argument("--out",  default="workhours_plot",
                   help="Output file stem — .png and .pdf are appended")
    args = p.parse_args()

    date_from = datetime.strptime(args.date_from, "%Y-%m-%d").date() if args.date_from else None
    date_to   = datetime.strptime(args.date_to,   "%Y-%m-%d").date() if args.date_to   else None

    rows = load_daily(Path(args.csv), date_from, date_to)
    print(f"Days loaded: {len(rows)}")
    if not rows:
        print("No data in range.")
        return

    build_figure(rows, date_from, args.bins, args.out)


if __name__ == "__main__":
    main()
