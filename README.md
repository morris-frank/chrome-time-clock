# Chrome Time Clock

Infer approximate workday start/end from Chrome browser history, and plot or merge work hours.

This package provides tools to extract, analyze, and visualize your working hours based on your browser history. It supports Google Chrome, Chromium, and Brave browsers across macOS, Windows, and Linux.

## Installation

You can install the package locally in editable mode (for development) or normally:

```bash
pip install -e .
```

This will automatically install the package and its dependencies (such as `matplotlib`).

## Command Line Interface (CLI)

The package installs a unified CLI command `chrome-time-clock`, along with individual command shortcuts.

### 1. Extracting Work Hours

Infer your workday start and end times from browser history:

```bash
# Using the unified CLI
chrome-time-clock extract --browser chrome --profile Default --out ./export --markdown

# Or using the direct shortcut
chrome-workhours --browser chrome --profile Default --out ./export --markdown
```

**Options:**

- `--browser`: `chrome`, `chromium`, or `brave` (default: `chrome`)
- `--profile`: Profile name, e.g., `Default` or `Profile 1` (default: `Default`)
- `--history-db`: Direct path to a History SQLite file (overrides browser/profile auto-resolution)
- `--from`: Start date `YYYY-MM-DD` (inclusive)
- `--to`: End date `YYYY-MM-DD` (inclusive)
- `--timezone`: IANA timezone name (default: `Europe/Amsterdam`)
- `--gap-minutes`: Inactivity threshold in minutes to separate active blocks (default: `60`)
- `--out`: Output directory for CSV files (default: `./chrome_workhours_export`)
- `--markdown`: Also generate a `daily_summary.md` table in the output directory

### 2. Plotting Work Hours

Generate beautiful work-hour timelines and histograms in a dark theme:

```bash
# Using the unified CLI
chrome-time-clock plot ./export/daily_summary.csv --from 2026-02-22 --out workhours_plot

# Or using the direct shortcut
plot-workhours ./export/daily_summary.csv --from 2026-02-22 --out workhours_plot
```

**Options:**

- `--from`: Start date `YYYY-MM-DD` (inclusive) (default: `2026-02-22`)
- `--to`: End date `YYYY-MM-DD` (inclusive)
- `--bins`: Number of bins for histograms (default: `15`)
- `--out`: Output file stem; `.png` and `.pdf` are appended (default: `workhours_plot`)
- `--show`: Display the plot window interactively

### 3. Merging Work Hours

Merge multiple `blocks.csv` files, collapsing overlapping time intervals (useful if you work across multiple machines or profiles):

```bash
# Using the unified CLI
chrome-time-clock merge blocks_laptop.csv blocks_desktop.csv --out-blocks merged_blocks.csv --out-daily merged_daily.csv

# Or using the direct shortcut
merge-blocks blocks_laptop.csv blocks_desktop.csv --out-blocks merged_blocks.csv --out-daily merged_daily.csv
```

---

## Programmatic Python API

You can also use the package programmatically in your own Python scripts:

```python
from datetime import date
from chrome_time_clock import extract_workhours, plot_workhours, merge_blocks

# 1. Extract
daily_rows, block_rows, warnings = extract_workhours(
    browser="chrome",
    profile="Default",
    date_from=date(2026, 6, 1),
    timezone_str="Europe/Amsterdam"
)

# 2. Plot
plot_workhours(
    csv_path="./export/daily_summary.csv",
    date_from=date(2026, 6, 1),
    out_stem="my_workhours_plot"
)

# 3. Merge
merge_blocks(
    files=["blocks_laptop.csv", "blocks_desktop.csv"],
    out_blocks="merged_blocks.csv",
    out_daily="merged_daily.csv"
)
```

