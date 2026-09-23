<img src="brand/icon/icon-chrome-time-clock-on-obsidian-1024.png" align="left" width="128" hspace="16" alt="chrome-time-clock icon">

<h3>chrome-time-clock</h3>

<p>
  <sub>YOUR BROWSER ALREADY KEPT THE TIMESHEET</sub>
  <br>
  <strong>Infer workday start and end from Chrome, Chromium or Brave history, then plot or merge the hours.</strong>
  <br>
  <br>
  <a href="https://pypi.org/project/chrome-time-clock/"><img src="https://img.shields.io/pypi/v/chrome-time-clock?style=flat-square&amp;color=3775A9&amp;logo=pypi&amp;logoColor=white&amp;labelColor=2D2825" alt="PyPI version"></a>
  <img src="https://img.shields.io/badge/python-%E2%89%A53.9-D78A7A?style=flat-square&amp;labelColor=2D2825" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/browsers-Chrome%20%C2%B7%20Chromium%20%C2%B7%20Brave-D78A7A?style=flat-square&amp;labelColor=2D2825" alt="Chrome, Chromium, Brave">
  <img src="https://img.shields.io/badge/OS-macOS%20%C2%B7%20Windows%20%C2%B7%20Linux-7E9688?style=flat-square&amp;labelColor=2D2825" alt="macOS, Windows, Linux">
  <img src="https://img.shields.io/badge/license-MIT-7E9688?style=flat-square&amp;labelColor=2D2825" alt="MIT license">
</p>

<br clear="left">

```sh
uv tool install chrome-time-clock                      # or: pipx install chrome-time-clock
chrome-time-clock extract --out ./export --markdown     # history → daily_summary.csv (+ .md)
chrome-time-clock plot ./export/daily_summary.csv       # timeline + histograms, .png and .pdf
chrome-time-clock merge laptop.csv desktop.csv          # union of blocks across machines
```

Everything runs locally against a copy of the browser's History SQLite file; nothing leaves the machine.

## Extract

Groups history visits into active blocks, split wherever the gap exceeds `--gap-minutes`, and reports each day's first and last block.

| Option | Default | |
|---|---|---|
| `--browser` | `chrome` | `chrome`, `chromium` or `brave` |
| `--profile` | `Default` | e.g. `Profile 1` |
| `--history-db` | — | a History file directly; overrides browser/profile |
| `--from` / `--to` | — | `YYYY-MM-DD`, inclusive |
| `--timezone` | `Europe/Amsterdam` | IANA name |
| `--gap-minutes` | `60` | inactivity that ends a block |
| `--out` | `./chrome_workhours_export` | CSV output directory |
| `--markdown` | off | also write `daily_summary.md` |

## Plot

Dark-theme timeline and start/end histograms from `daily_summary.csv`.

| Option | Default | |
|---|---|---|
| `--from` / `--to` | `2026-02-22` / — | `YYYY-MM-DD`, inclusive |
| `--bins` | `15` | histogram bins |
| `--out` | `workhours_plot` | file stem; `.png` and `.pdf` appended |
| `--show` | off | open an interactive window |

## Merge

Combines several `blocks.csv` files — one per machine or profile — collapsing overlapping intervals:

```sh
chrome-time-clock merge a.csv b.csv --out-blocks merged_blocks.csv --out-daily merged_daily.csv
```

Each subcommand also has a standalone shortcut: `chrome-workhours`, `plot-workhours`, `merge-blocks`.

## Python API

```python
from datetime import date
from chrome_time_clock import extract_workhours, plot_workhours, merge_blocks

daily, blocks, warnings = extract_workhours(browser="chrome", profile="Default",
                                            date_from=date(2026, 6, 1), timezone_str="Europe/Amsterdam")
plot_workhours(csv_path="./export/daily_summary.csv", date_from=date(2026, 6, 1), out_stem="plot")
merge_blocks(files=["a.csv", "b.csv"], out_blocks="merged_blocks.csv", out_daily="merged_daily.csv")
```
