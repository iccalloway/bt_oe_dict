"""Find morphemes in parsed/ that still transcribe with unresolved K/G.

An unmarked ⟨c⟩ or ⟨g⟩ next to a front vowel is emitted as capital K/G by
`phonology.transcribe` when the palatal-vs-velar contrast can't be decided
from spelling alone. Entries in `morphemes.json` override that resolution.
This script walks every parsed JSON, splits each citation form on the
editor's hyphens (so `ǣg-mang` contributes the morphemes `ǣg` and `mang`
separately), transcribes each morpheme, and lists those whose transcription
still contains K or G — sorted by frequency so you can pick the highest-
impact additions to add to `morphemes.json`.

Usage:
    uv run find_ambiguous.py            # print all
    uv run find_ambiguous.py --top 50   # print the 50 most frequent
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter

from phonology import transcribe
from write_xml import normalize, _PRON_WORD_RE


def _has_ambiguous(t: str) -> bool:
    return "K" in t or "G" in t


def collect(parsed_dir: str) -> Counter[tuple[str, str]]:
    """Return a counter keyed by (morpheme, transcription) for unresolved cases."""
    counts: Counter[tuple[str, str]] = Counter()
    for path in sorted(glob.glob(os.path.join(parsed_dir, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        forms = [d.get("citation_form", "")] + list(d.get("variant_forms", []) or [])
        seen_here: set[tuple[str, str]] = set()
        for form in forms:
            for word in _PRON_WORD_RE.findall(normalize(form) or ""):
                for morph in word.split("-"):
                    if not morph:
                        continue
                    try:
                        t = transcribe(morph)
                    except Exception:
                        continue
                    if _has_ambiguous(t):
                        key = (morph, t)
                        # Dedupe within a single entry — variant forms often
                        # repeat the same morpheme and would inflate counts.
                        if key in seen_here:
                            continue
                        seen_here.add(key)
                        counts[key] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--parsed-dir", default="./parsed/", help="Directory of parsed JSONs")
    ap.add_argument("--top", type=int, default=None, help="Only show the N most common")
    args = ap.parse_args(argv)

    counts = collect(args.parsed_dir)
    if not counts:
        print("No unresolved K/G morphemes found.")
        return 0

    items = counts.most_common(args.top)
    w_morph = max(len(m) for m, _ in (k for k, _ in items))
    w_trans = max(len(t) for _, t in (k for k, _ in items))
    total_unique = len(counts)
    total_occurrences = sum(counts.values())

    print(f"{total_unique} unique unresolved morphemes ({total_occurrences} occurrences)\n")
    print(f"{'morpheme':<{w_morph}}  {'transcription':<{w_trans}}  count")
    print("-" * (w_morph + w_trans + 12))
    for (morph, t), n in items:
        print(f"{morph:<{w_morph}}  {t:<{w_trans}}  {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
