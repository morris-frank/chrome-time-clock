"""Unified command-line interface for chrome-time-clock."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from chrome_time_clock.extractor import DEFAULT_GAP_MINUTES, DEFAULT_OUT_DIR, DEFAULT_PROFILE, DEFAULT_TIMEZONE, extract_workhours, write_csv, write_markdown
from chrome_time_clock.merger import merge_blocks
from chrome_time_clock.plotter import plot_workhours


def main() -> None:
    """Main entry point for the unified chrome-time-clock CLI."""
    parser = argparse.ArgumentParser(
        prog="chrome-time-clock",
        description="Chrome Time Clock: Infer, plot, and merge work hours from browser history.",
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True, title="subcommands")

    # ── Extract Subcommand ────────────────────────────────────────────────────
    extract_parser = subparsers.add_parser(
        "extract",
        help="Infer workday start/end from browser history",
        description="Infer workday start/end from Chrome/Chromium/Brave browser history.",
    )
    extract_parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help=f"Browser profile name (default: {DEFAULT_PROFILE})",
    )
    extract_parser.add_argument(
        "--browser",
        default="chrome",
        choices=["chrome", "chromium", "brave"],
        help="Browser type (default: chrome)",
    )
    extract_parser.add_argument(
        "--history-db",
        default=None,
        help="Direct path to History SQLite file (overrides browser/profile resolution)",
    )
    extract_parser.add_argument(
        "--from",
        dest="date_from",
        default=None,
        help="Start date YYYY-MM-DD (inclusive)",
    )
    extract_parser.add_argument(
        "--to",
        dest="date_to",
        default=None,
        help="End date YYYY-MM-DD (inclusive)",
    )
    extract_parser.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE,
        help=f"IANA timezone (default: {DEFAULT_TIMEZONE})",
    )
    extract_parser.add_argument(
        "--gap-minutes",
        type=int,
        default=DEFAULT_GAP_MINUTES,
        help=f"Inactivity gap threshold in minutes (default: {DEFAULT_GAP_MINUTES})",
    )
    extract_parser.add_argument(
        "--out",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUT_DIR})",
    )
    extract_parser.add_argument(
        "--markdown",
        action="store_true",
        help="Also write daily_summary.md inside the output directory",
    )

    # ── Plot Subcommand ───────────────────────────────────────────────────────
    plot_parser = subparsers.add_parser(
        "plot",
        help="Work-hour timelines and histograms",
        description="Generate work-hour timelines and histograms in dark Soilytix style.",
    )
    plot_parser.add_argument(
        "csv",
        help="Path to the daily summary CSV file",
    )
    plot_parser.add_argument(
        "--from",
        dest="date_from",
        default="2026-02-22",
        help="Start date YYYY-MM-DD (inclusive) (default: 2026-02-22)",
    )
    plot_parser.add_argument(
        "--to",
        dest="date_to",
        default=None,
        help="End date YYYY-MM-DD (inclusive)",
    )
    plot_parser.add_argument(
        "--bins",
        type=int,
        default=15,
        help="Number of bins for histograms (default: 15)",
    )
    plot_parser.add_argument(
        "--out",
        default="workhours_plot",
        help="Output file stem — .png and .pdf are appended (default: workhours_plot)",
    )
    plot_parser.add_argument(
        "--show",
        action="store_true",
        help="Display the plot window",
    )

    # ── Merge Subcommand ──────────────────────────────────────────────────────
    merge_parser = subparsers.add_parser(
        "merge",
        help="Merge blocks.csv files",
        description="Merge multiple blocks.csv files, collapsing overlapping time intervals.",
    )
    merge_parser.add_argument(
        "files",
        nargs="+",
        help="List of blocks.csv files to merge",
    )
    merge_parser.add_argument(
        "--out-blocks",
        default="merged_blocks.csv",
        help="Output filename for merged blocks (default: merged_blocks.csv)",
    )
    merge_parser.add_argument(
        "--out-daily",
        default="merged_daily.csv",
        help="Output filename for derived daily summary (default: merged_daily.csv)",
    )

    # Parse arguments
    args = parser.parse_args()

    try:
        if args.command == "extract":
            date_from = (
                datetime.strptime(args.date_from, "%Y-%m-%d").date() if args.date_from else None
            )
            date_to = (
                datetime.strptime(args.date_to, "%Y-%m-%d").date() if args.date_to else None
            )

            daily_rows, block_rows, warnings = extract_workhours(
                browser=args.browser,
                profile=args.profile,
                history_db=args.history_db,
                date_from=date_from,
                date_to=date_to,
                timezone_str=args.timezone,
                gap_minutes=args.gap_minutes,
            )

            if not daily_rows:
                print("No visits found after filtering. Nothing to do.")
                return

            print(f"Days summarised: {len(daily_rows)}")
            for w in warnings:
                print(f"  {w}")

            out_dir = Path(args.out)
            out_dir.mkdir(parents=True, exist_ok=True)

            daily_path = out_dir / "daily_summary.csv"
            blocks_path = out_dir / "blocks.csv"

            write_csv(
                daily_rows,
                daily_path,
                ["date", "first_seen", "last_seen", "gross_span_hours", "active_block_hours", "n_blocks", "n_visits"],
            )
            write_csv(
                block_rows,
                blocks_path,
                ["date", "block_start", "block_end", "duration_hours", "n_visits"],
            )

            if args.markdown:
                md_path = out_dir / "daily_summary.md"
                write_markdown(daily_rows, md_path)
                print(f"Markdown written to:  {md_path}")

            print(f"Output written to: {out_dir.resolve()}")
            print(f"  {daily_path.name}: {len(daily_rows)} days")
            print(f"  {blocks_path.name}: {len(block_rows)} blocks")

        elif args.command == "plot":
            date_from = (
                datetime.strptime(args.date_from, "%Y-%m-%d").date() if args.date_from else None
            )
            date_to = (
                datetime.strptime(args.date_to, "%Y-%m-%d").date() if args.date_to else None
            )

            plot_workhours(
                csv_path=args.csv,
                date_from=date_from,
                date_to=date_to,
                bins=args.bins,
                out_stem=args.out,
                show=args.show,
            )

        elif args.command == "merge":
            merge_blocks(
                files=args.files,
                out_blocks=args.out_blocks,
                out_daily=args.out_daily,
            )
            print(f"Successfully merged {len(args.files)} file(s).")
            print(f"Written: {args.out_blocks}")
            print(f"Written: {args.out_daily}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
