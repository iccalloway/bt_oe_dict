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


def read_entries(path: str = "./bt_text.txt", limit: int | None = 1000):
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
        if src:
            seen.add(src)
    return seen


def main():
    out_dir = Path("parsed")
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
            payload = entry.model_dump(mode="json") | {"source_text": entry_text}
            with open(out_dir / f"{entry.citation_form}.json", "w", encoding="utf8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        seen_sources.add(entry_text)

    if failures:
        print(f"\n{len(failures)} failures:")
        for head, err in failures:
            print(f"  {head!r}: {err}")


if __name__ == "__main__":
    main()
