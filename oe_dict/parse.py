import json
import random
from pathlib import Path

import tqdm
from pydantic import ValidationError

from llm import parse_structured
from schema import EntryBatch


SYSTEM = (
    "You are parsing entries from Bosworth-Toller's Anglo-Saxon Dictionary. "
    "Call the `record_entry` tool exactly once with the parsed batch. "
    "Follow the field descriptions in the tool schema — copy source text verbatim "
    "(never translate or normalize), and use null when a field is not present.\n\n"
    "Most source blocks are a single entry; return `entries` with one item. "
    "Occasionally a block collapses multiple stub cross-references into one line "
    "(e.g. 'á-bet, beþecian, -bicgan. v. á, B. IV, -bedecian, -bycgan.') — split "
    "each headword and its target into its own OldEnglishEntry.\n\n"
    "Entries prefixed with 'Add:--' (e.g. 'á-bannan. Add:-- Ábanie...') are "
    "supplemental additions from BT's supplement volume. Treat 'Add:--' as a "
    "source marker to strip and parse the rest as a normal entry.\n\n"
    "Within a supplement entry, the pattern `<Roman>. add :--` or "
    "`<Roman>. Add :--` (e.g. 'rihte. I. add :-- Smire mid...') means 'add the "
    "following quotations to sense N of the main-dictionary entry; no new gloss'. "
    "In that case set `meaning` to null (do NOT write literal 'add') and populate "
    "`quotations` only."
)


_ROOT = Path(__file__).parent.parent


def read_entries(path: str | None = None, limit: int | None = 1000):
    if path is None:
        path = str(_ROOT / "resources" / "bt_text.txt")
    with open(path, "r") as f:
        entries = f.read().split("\n\n")
        print(len(entries))
        random.shuffle(entries)

    if limit is not None:
        entries = entries[:limit]
    for e in entries:
        if e.strip():
            yield e


def _load_seen_source_texts(out_dir: Path) -> set[str]:
    seen = set()
    for path in out_dir.glob("*.json"):
        try:
            with open(path, "r", encoding="utf8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        src = data.get("source_text")
        if isinstance(src, list):
            seen.update(s for s in src if s)
        elif src:
            seen.add(src)
    return seen


def _canonical(item) -> str:
    """Stable string key for deduping list items (handles nested dicts)."""
    return json.dumps(item, sort_keys=True, ensure_ascii=False)


def _union(a: list, b: list) -> list:
    """Concatenate two lists, dropping duplicates by canonical JSON form,
    preserving first-seen order."""
    out: list = []
    seen: set[str] = set()
    for item in list(a) + list(b):
        key = _canonical(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _merge_entries(existing: dict, new: dict, source_text: str) -> dict:
    """Merge `new` into `existing` (both post-`model_dump` dicts sharing a
    citation_form). Unions list fields, preserves source_text history as a
    list so the resume-skip check remembers every block that fed this entry."""
    existing_sources = existing.get("source_text")
    if isinstance(existing_sources, list):
        sources = list(existing_sources)
    elif existing_sources:
        sources = [existing_sources]
    else:
        sources = []
    if source_text and source_text not in sources:
        sources.append(source_text)

    return {
        "citation_form": new.get("citation_form") or existing.get("citation_form"),
        "variant_forms": _union(existing.get("variant_forms", []), new.get("variant_forms", [])),
        "definitions": _union(existing.get("definitions", []), new.get("definitions", [])),
        "cross_references": _union(existing.get("cross_references", []), new.get("cross_references", [])),
        "source_text": sources,
    }


def _merge_or_write(out_dir: Path, entry, source_text: str) -> None:
    """Write an entry to `parsed/{citation_form}.json`, merging into any
    existing file rather than overwriting it."""
    path = out_dir / f"{entry.citation_form}.json"
    new_payload = entry.model_dump(mode="json")
    if path.exists():
        try:
            with open(path, "r", encoding="utf8") as f:
                existing = json.load(f)
        except (OSError, json.JSONDecodeError):
            existing = None
        if isinstance(existing, dict):
            merged = _merge_entries(existing, new_payload, source_text)
        else:
            merged = new_payload | {"source_text": [source_text]}
    else:
        merged = new_payload | {"source_text": [source_text]}
    with open(path, "w", encoding="utf8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)


def main():
    out_dir = Path(__file__).parent / "parsed_entries"
    out_dir.mkdir(exist_ok=True)
    seen_sources = _load_seen_source_texts(out_dir)
    failures = []

    for entry_text in tqdm.tqdm(list(read_entries())):
        if entry_text in seen_sources:
            print(f"skipping already-parsed entry: {entry_text[:60]!r}")
            continue
        try:
            batch = parse_structured(SYSTEM, entry_text, EntryBatch)
        except (ValidationError, RuntimeError) as e:
            failures.append((entry_text[:60], str(e)))
            continue

        for entry in batch.entries:
            _merge_or_write(out_dir, entry, entry_text)
        seen_sources.add(entry_text)

    if failures:
        print(f"\n{len(failures)} failures:")
        for head, err in failures:
            print(f"  {head!r}: {err}")


if __name__ == "__main__":
    main()
