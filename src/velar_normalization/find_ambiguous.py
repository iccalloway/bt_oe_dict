"""Find parsed entries whose citation form transcribes with unresolved K/G.

Any Old English word whose transcription contains uppercase K or G still has
an ambiguous unmarked ⟨c⟩ or ⟨g⟩ that neither the morpheme lookup
(`morphemes.json`) nor a manual correction in `corrections.csv` has
disambiguated.

Output:
- Terminal: sorted list of unresolved words with their transcriptions and counts.
- `corrections.csv`: two columns (`original`, `corrected`), preserving any
  manual edits from previous runs. Add hyphens (or otherwise reshape the
  spelling) in column B to force morpheme segmentation, e.g.

      original,corrected
      þeōdendlīc,þeōdend-līc

  `write_xml.py` looks up column A in this CSV and, when found, transcribes
  the value in column B instead — so `līc` (which is in `morphemes.json`)
  gets its palatal /tʃ/ instead of being flagged as ambiguous /K/.

Usage (from project root):
    uv run src/velar_normalization/find_ambiguous.py
    uv run src/velar_normalization/find_ambiguous.py --top 50
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

# Allow importing project-root modules when run as `uv run velar_normalization/find_ambiguous.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonology import transcribe  # noqa: E402
from write_xml import normalize, _PRON_WORD_RE  # noqa: E402


CSV_PATH = Path(__file__).parent / "corrections.csv"


def _has_ambiguous(t: str) -> bool:
    return "K" in t or "G" in t


def load_corrections() -> dict[str, str]:
    """Read existing corrections.csv into {original: corrected}."""
    if not CSV_PATH.exists():
        return {}
    out: dict[str, str] = {}
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if len(row) >= 2 and row[0]:
                out[row[0]] = row[1] if row[1] else row[0]
    return out


def write_corrections(mapping: dict[str, str]) -> None:
    """Write {original: corrected} back to corrections.csv, sorted by original."""
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["original", "corrected"])
        for k in sorted(mapping):
            w.writerow([k, mapping[k]])


def collect(parsed_dir: str, existing: dict[str, str]) -> Counter[tuple[str, str, str]]:
    """Counter keyed by (original, corrected, transcription) for unresolved words.

    `corrected` reflects the user's CSV entry (identity by default).
    `transcription` is what `transcribe` returns for the corrected form —
    which still contains K or G, or the word wouldn't be in this list."""
    counts: Counter[tuple[str, str, str]] = Counter()
    for path in sorted(glob.glob(os.path.join(parsed_dir, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        forms = [d.get("citation_form", "")] + list(d.get("variant_forms", []) or [])
        seen: set[tuple[str, str, str]] = set()
        for form in forms:
            for word in _PRON_WORD_RE.findall(normalize(form) or ""):
                corrected = existing.get(word, word)
                try:
                    t = transcribe(corrected)
                except Exception:
                    continue
                if not _has_ambiguous(t):
                    continue
                key = (word, corrected, t)
                if key in seen:
                    continue
                seen.add(key)
                counts[key] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    default_parsed = str(Path(__file__).resolve().parent.parent.parent / "parsed")
    ap.add_argument("--parsed-dir", default=default_parsed, help="Directory of parsed JSONs")
    ap.add_argument("--top", type=int, default=None, help="Only show the N most common on stdout")
    args = ap.parse_args(argv)

    existing = load_corrections()
    counts = collect(args.parsed_dir, existing)

    # Always write the CSV: every currently-unresolved word gets a row,
    # preserving the user's manual correction (or identity default).
    mapping = {orig: corr for (orig, corr, _), _ in counts.items()}
    write_corrections(mapping)

    if not counts:
        print(f"No unresolved K/G words. Wrote empty {CSV_PATH.name}.")
        return 0

    items = counts.most_common(args.top)
    w_orig = max(len(o) for (o, _, _), _ in items)
    w_corr = max(len(c) for (_, c, _), _ in items)
    w_trans = max(len(t) for (_, _, t), _ in items)
    total_unique = len(counts)
    total_occurrences = sum(counts.values())

    rel_csv = os.path.relpath(CSV_PATH)
    print(f"{total_unique} unresolved words ({total_occurrences} occurrences) → {rel_csv}\n")
    header = f"{'original':<{w_orig}}  {'corrected':<{w_corr}}  {'transcription':<{w_trans}}  count"
    print(header)
    print("-" * len(header))
    for (o, c, t), n in items:
        print(f"{o:<{w_orig}}  {c:<{w_corr}}  {t:<{w_trans}}  {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
