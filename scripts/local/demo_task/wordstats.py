"""Tiny word-frequency library used by report.py."""

from collections import Counter


def count_words(text):
    """Return a Counter of lowercase words."""
    return Counter(text.lower().split())


def top_words(counts, n):
    """Return the n most common (word, count) pairs, ties broken alphabetically."""
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[: n - 1]
