"""Phase 4 — invert into English lemma → OE equivalents grouped by synset.

Reads `disambiguated.jsonl`, groups by (english_lemma, pos), then within
each group by synset_id, and writes one JSON per English lemma into
`english_dict/parsed_entries/{english_lemma}.{pos}.json`.

Within each synset's `oe_equivalents`, entries are deduped by `oe_lemma`
(different sense-paths of the same OE word collapse into one, unioning
their Latin glosses and attestations).

Usage (from project root):
    uv run rev_dict/invert.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import nltk
import tqdm
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import RegexpTokenizer

_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(_ROOT / "oe_dict"))

from schema import (  # noqa: E402
    DisambiguatedRow,
    OEEquivalent,
    QuotationRef,
    ReverseEntry,
    ReverseSense,
)


# Defensive: WordNetLemmatizer lazy-loads the corpus on first call; if it's
# missing we want a clean error at startup, not mid-loop.
try:
    nltk.data.find("corpora/wordnet")
except LookupError:
    nltk.download("wordnet", quiet=True)

_LEMMATIZER = WordNetLemmatizer()
_TOKEN_RE = RegexpTokenizer(r"[A-Za-z]+")


def _lemma_set(text: str) -> set[str]:
    """Lowercase alphabetic tokens of `text`, each lemmatized under noun,
    verb, and adjective POS. The union catches inflections without needing a
    POS tagger — 'deeds' → {deed}, 'ran' → {run, ran}, 'better' → {better, good}."""
    out: set[str] = set()
    for w in _TOKEN_RE.tokenize(text.lower()):
        out.add(_LEMMATIZER.lemmatize(w, "n"))
        out.add(_LEMMATIZER.lemmatize(w, "v"))
        out.add(_LEMMATIZER.lemmatize(w, "a"))
    return out


def _quote_matches(english_lemma: str, quotation: QuotationRef) -> bool:
    """True iff every alphabetic token in `english_lemma` appears (as a lemma)
    in the quotation's English translation. Multi-word lemmas like 'young man'
    require both 'young' and 'man' to be present in the translation."""
    if not quotation.english:
        return False
    target_tokens = _TOKEN_RE.tokenize(english_lemma.lower())
    if not target_tokens:
        return False
    target = {_LEMMATIZER.lemmatize(w, "n") for w in target_tokens}
    return target.issubset(_lemma_set(quotation.english))


_IN_PATH = Path(__file__).parent / "disambiguated.jsonl"
_OUT_DIR = Path(__file__).parent / "parsed_entries"

# Filesystem-safe filename slug.
_SLUG_RE = re.compile(r"[^A-Za-z0-9_\-]+")


def _slugify(lemma: str) -> str:
    slug = _SLUG_RE.sub("_", lemma.strip())
    return slug or "_"


def _dedup_extend(dest: list[str], src: list[str]) -> None:
    seen = set(dest)
    for s in src:
        if s and s not in seen:
            seen.add(s)
            dest.append(s)


def _merge_equivalent(dest: OEEquivalent, row: DisambiguatedRow, filtered_quotes: list[QuotationRef]) -> None:
    """Fold a new disambiguated row's Latin/attestations/quotations into an existing OE entry.
    `filtered_quotes` is the row's quotations already narrowed to those matching the
    target English lemma."""
    _dedup_extend(dest.variants, row.token.variants)
    _dedup_extend(dest.latin_glosses, row.token.latin_anchors)
    _dedup_extend(dest.attestations, row.token.citations)
    # Dedupe quotations by OE text — same passage often appears once under
    # the top-level definition and again under a subsense.
    seen = {q.old_english for q in dest.quotations}
    for q in filtered_quotes:
        if q.old_english in seen:
            continue
        seen.add(q.old_english)
        dest.quotations.append(q)
    if dest.gender is None and row.token.gender:
        dest.gender = row.token.gender


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="in_path", default=str(_IN_PATH))
    ap.add_argument("--out-dir", default=str(_OUT_DIR))
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # buckets[(english_lemma, pos)][synset_id] -> {oe_lemma: OEEquivalent}
    buckets: dict[tuple[str, str], dict[str, dict[str, OEEquivalent]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    # buckets_defs[(english_lemma, pos)][synset_id] -> definition (str or None)
    buckets_defs: dict[tuple[str, str], dict[str, str | None]] = defaultdict(dict)

    with open(args.in_path, encoding="utf-8") as f:
        lines = f.readlines()

    for line in tqdm.tqdm(lines, desc="invert"):
        line = line.strip()
        if not line:
            continue
        row = DisambiguatedRow.model_validate_json(line)
        t = row.token
        key = (t.english_token, t.pos)
        # A quotation only belongs on this English entry if its English
        # translation actually contains the headword lemma.
        filtered = [q for q in t.quotations if _quote_matches(key[0], q)]
        sense_bucket = buckets[key][row.selected_synset_id]
        if t.oe_lemma in sense_bucket:
            _merge_equivalent(sense_bucket[t.oe_lemma], row, filtered)
        else:
            sense_bucket[t.oe_lemma] = OEEquivalent(
                oe_lemma=t.oe_lemma,
                pos=t.pos,
                gender=t.gender,
                variants=list(t.variants),
                latin_glosses=list(t.latin_anchors),
                attestations=list(t.citations),
                quotations=filtered,
            )
        # Record the WordNet definition (may be None for historical_unmapped).
        prev = buckets_defs[key].get(row.selected_synset_id)
        if prev is None and row.definition:
            buckets_defs[key][row.selected_synset_id] = row.definition
        elif row.selected_synset_id not in buckets_defs[key]:
            buckets_defs[key][row.selected_synset_id] = row.definition

    # Write one file per (english_lemma, pos). Sort senses: real synsets by ID,
    # then historical_unmapped last.
    n_files = 0
    for (english_lemma, pos), by_syn in buckets.items():
        def _sense_sort_key(sid: str):
            return (sid == "historical_unmapped", sid)

        senses = []
        for sid in sorted(by_syn.keys(), key=_sense_sort_key):
            equivs = sorted(by_syn[sid].values(), key=lambda e: e.oe_lemma.lower())
            senses.append(
                ReverseSense(
                    synset_id=sid,
                    definition=buckets_defs[(english_lemma, pos)].get(sid),
                    oe_equivalents=equivs,
                )
            )
        entry = ReverseEntry(english_lemma=english_lemma, pos=pos, senses=senses)
        out_path = out_dir / f"{_slugify(english_lemma)}.{pos}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(entry.model_dump_json(indent=2))
        n_files += 1

    print(f"Wrote {n_files} reverse-dictionary files to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
