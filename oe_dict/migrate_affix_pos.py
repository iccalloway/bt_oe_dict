"""One-shot migration: re-parse affix entries so they carry `AffixPOS`.

Entries with a leading or trailing hyphen in their citation form (`-icge`,
`-el`, `ge-`, `of-`, …) were parsed before `AffixPOS` existed — the LLM
categorized them as whatever else fit (noun, adverb, conjunction). Now that
`src/schema.py` has an `affix` category, feed each affected entry's
`source_text` back through `parse_structured` with the current schema so the
LLM re-classifies. Preserves any accumulated `source_text` history.

Idempotent — skips entries whose Definitions all already have
`pos.category == "affix"`. Run once:

    uv run src/migrate_affix_pos.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import tqdm
from pydantic import ValidationError

from llm import parse_structured
from parse import SYSTEM, _merge_entries
from schema import EntryBatch


_ROOT = Path(__file__).resolve().parent.parent
_PARSED = Path(__file__).parent / "parsed_entries"


def _is_affix_cf(citation_form: str) -> bool:
    return citation_form.startswith("-") or citation_form.endswith("-")


def _all_affix(defs: list[dict]) -> bool:
    return bool(defs) and all((d.get("pos") or {}).get("category") == "affix" for d in defs)


def _reparse_one(existing: dict) -> dict | None:
    """Re-parse an entry from its stored source_text blocks. Merges the LLM's
    output for each block using parse.py's own merge helper so multi-block
    entries keep their unioned form."""
    cf = existing.get("citation_form")
    if not cf:
        return None

    source_blocks = existing.get("source_text") or []
    if isinstance(source_blocks, str):
        source_blocks = [source_blocks]
    if not source_blocks:
        return None

    merged: dict | None = None
    for block in source_blocks:
        try:
            batch = parse_structured(SYSTEM, block, EntryBatch)
        except (ValidationError, RuntimeError) as e:
            tqdm.tqdm.write(f"[fail] {cf}: {e}")
            return None

        # A block may split into multiple headwords; pick the one that
        # matches our citation_form.
        picked = None
        for ent in batch.entries:
            if ent.citation_form == cf:
                picked = ent
                break
        if picked is None:
            tqdm.tqdm.write(f"[skip] {cf}: LLM output did not include this citation form")
            return None

        payload = picked.model_dump(mode="json")
        if merged is None:
            merged = payload | {"source_text": [block]}
        else:
            merged = _merge_entries(merged, payload, block)

    return merged


def main() -> int:
    files = sorted(_PARSED.glob("*.json"))
    affix_files = []
    for p in files:
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        cf = data.get("citation_form") or ""
        if not _is_affix_cf(cf):
            continue
        if _all_affix(data.get("definitions") or []):
            continue
        affix_files.append((p, data))

    print(f"{len(affix_files)} affix entries need re-parsing.")
    n_ok = 0
    for path, data in tqdm.tqdm(affix_files, desc="re-parse"):
        new_data = _reparse_one(data)
        if new_data is None:
            continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        n_ok += 1

    print(f"Rewrote {n_ok} / {len(affix_files)} affix files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
