"""Render a word-frequency report from a text file."""

from pathlib import Path

from wordstats import count_words, top_words


def load_text(path):
    return Path(path).read_bytes()


def render_report(path, n=3):
    counts = count_words(load_text(path))
    return "\n".join(f"{word} {count}" for word, count in top_words(counts, n))
