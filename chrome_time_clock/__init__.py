"""
Chrome Time Clock

Infer approximate workday start/end from Chrome browser history and plot/merge work hours.
"""

from chrome_time_clock.extractor import extract_workhours
from chrome_time_clock.merger import merge_blocks
from chrome_time_clock.plotter import plot_workhours

__version__ = "0.1.0"

__all__ = [
    "extract_workhours",
    "plot_workhours",
    "merge_blocks",
]
