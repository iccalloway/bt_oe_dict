"""Phase 2 — WordNet candidate generation.

For each row in `gloss_tokens.jsonl`, look up the English lemma in WordNet
filtered by POS. Rows split into three buckets:

- `unmapped`:   0 candidates → the LLM can't help; drop to the historical
                fallback synset in Phase 4.
- `monosemous`: exactly 1 candidate → auto-resolved, no Phase 3 LLM call.
- `polysemous`: ≥2 candidates → enqueued for Phase 3 disambiguation.

The output `candidates.jsonl` carries the original GlossToken plus the
WordNet candidate list plus the bucket tag.

Usage (from project root):
    uv run rev_dict/candidates.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import tqdm
from nltk.corpus import wordnet as wn

_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(_ROOT / "oe_dict"))

from schema import CandidateSet, CandidateSynset, GlossToken  # noqa: E402


_IN_PATH = Path(__file__).parent / "gloss_tokens.jsonl"
_OUT_PATH = Path(__file__).parent / "candidates.jsonl"

_POS_MAP = {"noun": "n", "verb": "v", "adjective": "a", "adverb": "r"}


def _wn_lookup(lemma: str, wn_pos: str) -> list[CandidateSynset]:
    # WordNet lemmas use underscores for spaces; we already lowercased in extract.py.
    query = lemma.replace(" ", "_")
    synsets = wn.synsets(query, pos=wn_pos)
    return [
        CandidateSynset(
            synset_id=s.name(),
            definition=s.definition(),
            examples=list(s.examples() or []),
            lemmas=[l.name() for l in s.lemmas()],
        )
        for s in synsets
    ]


def _bucket(n: int) -> str:
    if n == 0:
        return "unmapped"
    if n == 1:
        return "monosemous"
    return "polysemous"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="in_path", default=str(_IN_PATH))
    ap.add_argument("--out", default=str(_OUT_PATH))
    ap.add_argument("--limit", type=int, default=None, help="Process only the first N rows.")
    args = ap.parse_args(argv)

    with open(args.in_path, encoding="utf-8") as f:
        lines = f.readlines()
    if args.limit is not None:
        lines = lines[: args.limit]

    stats: Counter[str] = Counter()
    n_written = 0
    with open(args.out, "w", encoding="utf-8") as out:
        for line in tqdm.tqdm(lines, desc="candidates"):
            line = line.strip()
            if not line:
                continue
            token = GlossToken.model_validate_json(line)
            wn_pos = _POS_MAP.get(token.pos)
            if wn_pos is None:
                # Should never happen — extract.py already filters to noun/verb.
                stats["skipped_pos"] += 1
                continue
            cands = _wn_lookup(token.english_token, wn_pos)
            status = _bucket(len(cands))
            stats[status] += 1
            row = CandidateSet(token=token, wn_pos=wn_pos, candidates=cands, status=status)
            out.write(row.model_dump_json() + "\n")
            n_written += 1

    print(f"Wrote {n_written} rows to {args.out}")
    print(f"  unmapped   : {stats['unmapped']}")
    print(f"  monosemous : {stats['monosemous']}  (auto-resolved, skip LLM)")
    print(f"  polysemous : {stats['polysemous']}  (queued for Phase 3)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
