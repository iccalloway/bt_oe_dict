"""Phase 3 — pick the right WordNet synset for polysemous rows.

Reads `candidates.jsonl` and writes `disambiguated.jsonl`:

- `unmapped`   rows pass through with `selected_synset_id = "historical_unmapped"`.
- `monosemous` rows pass through with the single candidate (confidence 1.0,
  rationale "monosemous").
- `polysemous` rows go to the LLM one at a time, with a prompt that includes
  the OE lemma, the specific English gloss, sibling glosses, Latin anchors,
  citations, and the numbered candidate list. Results cached under
  `rev_dict/cache/disambiguate/{sha}.json` keyed on (oe_lemma, english_token,
  sense_path, candidate synset ID list) — so tweaking the prompt without
  changing the candidate set still re-uses cache.

Usage (from project root):
    uv run rev_dict/disambiguate.py                # full pass
    uv run rev_dict/disambiguate.py --limit 10     # smoke test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import tqdm

_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(_ROOT / "oe_dict"))

from llm import parse_structured  # noqa: E402
from schema import CandidateSet, Disambiguation, DisambiguatedRow  # noqa: E402


_IN_PATH = Path(__file__).parent / "candidates.jsonl"
_OUT_PATH = Path(__file__).parent / "disambiguated.jsonl"
_CACHE_DIR = Path(__file__).parent / "cache" / "disambiguate"

_SYSTEM = (
    "You are a lexicographer disambiguating Old English dictionary entries "
    "against WordNet. You will be given one Old English lemma, one English "
    "gloss token from Bosworth-Toller, sibling glosses from the same "
    "definition, any Latin translations from the source (strong sense "
    "anchors), sample Old English quotations, and a numbered list of "
    "candidate WordNet synsets for the English lemma. Choose the synset "
    "whose meaning best matches how the Old English word is used in this "
    "definition.\n\n"
    "Rules:\n"
    "- `selected_synset_id` must be one of the offered candidate IDs, "
    "verbatim. If truly none fit (e.g. an archaic/theological sense with "
    "no modern WordNet analog), return the literal string "
    "'historical_unmapped'.\n"
    "- Prefer literal, concrete senses over metaphorical unless the Latin "
    "or quotations point to the metaphorical one.\n"
    "- Latin anchors trump English co-text when they disagree.\n"
    "- Call `record_entry` exactly once."
)


def _cache_key(oe_lemma: str, english_token: str, sense_path: str, cand_ids: list[str]) -> str:
    h = hashlib.sha256()
    payload = json.dumps(
        {"oe": oe_lemma, "en": english_token, "path": sense_path, "cands": sorted(cand_ids)},
        ensure_ascii=False,
    )
    h.update(payload.encode("utf-8"))
    return h.hexdigest()


def _read_cache(key: str) -> Disambiguation | None:
    path = _CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return Disambiguation.model_validate(json.load(f))
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(key: str, result: Disambiguation) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_DIR / f"{key}.json", "w", encoding="utf-8") as f:
        f.write(result.model_dump_json())


def _build_prompt(row: CandidateSet) -> str:
    t = row.token
    lines = [
        f"Old English lemma: {t.oe_lemma}",
        f"POS: {t.pos}" + (f" ({t.gender})" if t.gender else ""),
        f"English gloss token: {t.english_token}",
    ]
    if t.sibling_glosses:
        lines.append("Sibling glosses (same definition): " + " | ".join(t.sibling_glosses))
    if t.latin_anchors:
        # Cap to 4 to keep prompt bounded.
        lines.append("Latin anchors: " + " | ".join(t.latin_anchors[:4]))
    if t.citations:
        lines.append(f"Attestations: {', '.join(t.citations[:3])}")
    lines.append("")
    lines.append("Candidate WordNet synsets:")
    for i, c in enumerate(row.candidates, 1):
        example = f"  ex: {c.examples[0]}" if c.examples else ""
        lines.append(f"  {i}. {c.synset_id}: {c.definition}{example}")
    return "\n".join(lines)


def _resolve(row: CandidateSet) -> DisambiguatedRow:
    t = row.token
    if row.status == "unmapped":
        return DisambiguatedRow(
            token=t, wn_pos=row.wn_pos,
            selected_synset_id="historical_unmapped",
            definition=None, confidence=0.0,
            rationale="no WordNet candidates",
        )
    if row.status == "monosemous":
        c = row.candidates[0]
        return DisambiguatedRow(
            token=t, wn_pos=row.wn_pos,
            selected_synset_id=c.synset_id,
            definition=c.definition, confidence=1.0,
            rationale="monosemous",
        )

    # Polysemous → LLM
    cand_ids = [c.synset_id for c in row.candidates]
    key = _cache_key(t.oe_lemma, t.english_token, t.sense_path, cand_ids)
    result = _read_cache(key)
    if result is None:
        user = _build_prompt(row)
        result = parse_structured(_SYSTEM, user, Disambiguation, model="claude-sonnet-4-6", max_tokens=1024)
        _write_cache(key, result)

    # Look up definition for the selected synset if it's one of the candidates.
    selected = result.selected_synset_id
    definition = None
    for c in row.candidates:
        if c.synset_id == selected:
            definition = c.definition
            break
    # Guard: if the model returned something not in our list and not
    # 'historical_unmapped', coerce to unmapped so downstream stays consistent.
    if selected != "historical_unmapped" and definition is None:
        selected = "historical_unmapped"

    return DisambiguatedRow(
        token=t, wn_pos=row.wn_pos,
        selected_synset_id=selected,
        definition=definition,
        confidence=result.confidence,
        rationale=result.rationale,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="in_path", default=str(_IN_PATH))
    ap.add_argument("--out", default=str(_OUT_PATH))
    ap.add_argument("--limit", type=int, default=None, help="Process only the first N rows.")
    args = ap.parse_args(argv)

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    with open(args.in_path, encoding="utf-8") as f:
        lines = f.readlines()
    if args.limit is not None:
        lines = lines[: args.limit]

    stats: Counter[str] = Counter()
    n_llm_calls = 0
    failures: list[tuple[str, str]] = []

    with open(args.out, "w", encoding="utf-8") as out:
        for line in tqdm.tqdm(lines, desc="disambiguate"):
            line = line.strip()
            if not line:
                continue
            row = CandidateSet.model_validate_json(line)
            try:
                if row.status == "polysemous":
                    cand_ids = [c.synset_id for c in row.candidates]
                    key = _cache_key(row.token.oe_lemma, row.token.english_token, row.token.sense_path, cand_ids)
                    if _read_cache(key) is None:
                        n_llm_calls += 1
                resolved = _resolve(row)
            except Exception as e:
                failures.append((f"{row.token.oe_lemma}/{row.token.english_token}", str(e)))
                continue
            stats[row.status] += 1
            out.write(resolved.model_dump_json() + "\n")

    print(f"Wrote {sum(stats.values())} rows to {args.out}")
    print(f"  unmapped   : {stats['unmapped']}")
    print(f"  monosemous : {stats['monosemous']}")
    print(f"  polysemous : {stats['polysemous']}  (LLM calls this run: {n_llm_calls})")
    if failures:
        print(f"\n{len(failures)} failures:")
        for tag, err in failures[:10]:
            print(f"  {tag}: {err}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
