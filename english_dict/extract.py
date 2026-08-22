"""Phase 1 — walk `parsed/*.json` and emit one gloss-token row per extracted
English lemma, ready for WordNet lookup.

For each noun/verb definition with a non-null `meaning`, ask a small LLM
(Haiku) to turn the messy 19th-c. gloss into clean dictionary-form lemmas
(e.g. "hope, expectation of something desired" → ["hope", "expectation"]).
Results are cached under `rev_dict/cache/extract/{sha}.json` so repeated
gloss strings across entries cost nothing on re-run.

Usage (from project root):
    uv run rev_dict/extract.py                 # full corpus
    uv run rev_dict/extract.py --limit 20      # pilot
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
from pathlib import Path

import tqdm

_ROOT = Path(__file__).resolve().parent.parent
# Append (not insert) so the script's own dir (`rev_dict/`) still wins for
# `schema` — `oe_dict/schema.py` exists and would shadow `english_dict/schema.py`.
sys.path.append(str(_ROOT / "oe_dict"))

from llm import parse_structured  # noqa: E402
from schema import GlossToken, LookupLemmas, QuotationRef  # noqa: E402


_CACHE_DIR = Path(__file__).parent / "cache" / "extract"
_OUT_PATH = Path(__file__).parent / "gloss_tokens.jsonl"

# Bump when the extract prompt changes so old (permissive) results don't
# shadow new (stricter) ones. Old cache files stay on disk but become
# unreachable — safe rollback if we ever want to compare.
_PROMPT_VERSION = "v2"

# Only noun/verb in the first pass. Other categories (including "affix") are
# dropped early.
_ALLOWED_POS = {"noun", "verb"}

_SYSTEM_EXTRACT = (
    "You extract lookup-ready English lemmas from Bosworth-Toller Anglo-Saxon "
    "dictionary glosses so they can be queried against WordNet. Call the "
    "`record_entry` tool exactly once.\n\n"
    "CORE RULE — equivalence, not mention. Only extract lemmas that could "
    "stand alone as an English translation of the OE headword. If no single "
    "English lemma captures the meaning, return an empty list. Many OE words "
    "have no clean modern equivalent, and that's fine — a missing entry is "
    "better than a misleading one.\n\n"
    "DO NOT extract words that merely appear in the gloss as description, "
    "morphology, or usage context:\n"
    "- 'a suffix of nouns denoting a female agent' → []  (the OE word is a "
    "bound morpheme; it is not itself a female, an agent, or a suffix)\n"
    "- 'used to form nouns from verbs' → []  (metalinguistic; nothing to look up)\n"
    "- 'belonging to a household' → []  (the OE word describes a relationship, "
    "not the household itself)\n"
    "- 'name of a plant' → []  (unless the plant name is given; 'name of X' is "
    "a placeholder, not a translation)\n\n"
    "DO extract when the gloss lists direct English equivalents:\n"
    "- 'hope, expectation of something desired' → ['hope', 'expectation']\n"
    "- 'to take, receive, get, obtain' → ['take', 'receive', 'get', 'obtain']\n"
    "- 'a law, statute' → ['law', 'statute']\n\n"
    "Format:\n"
    "- Lowercase; singular for nouns; bare infinitive for verbs (no 'to').\n"
    "- Drop function words ('a', 'the', 'of', 'to'), parentheticals, and Latin.\n"
    "- One lemma per distinct sense-hint; drop paraphrasing modifiers "
    "('something desired' after 'expectation' contributes nothing new).\n"
    "- Never invent lemmas not present in the gloss."
)


def _cache_key(pos_category: str, meaning: str) -> str:
    h = hashlib.sha256()
    h.update(_PROMPT_VERSION.encode("utf-8"))
    h.update(b"\0")
    h.update(pos_category.encode("utf-8"))
    h.update(b"\0")
    h.update(meaning.encode("utf-8"))
    return h.hexdigest()


def _cached_lemmas(pos_category: str, meaning: str) -> list[str] | None:
    key = _cache_key(pos_category, meaning)
    path = _CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)["lemmas"]
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def _write_cache(pos_category: str, meaning: str, lemmas: list[str]) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(pos_category, meaning)
    path = _CACHE_DIR / f"{key}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"pos": pos_category, "meaning": meaning, "lemmas": lemmas}, f, ensure_ascii=False)


def extract_lemmas(pos_category: str, meaning: str) -> list[str]:
    """LLM-extract dictionary-form English lemmas from a BT gloss, with cache."""
    cached = _cached_lemmas(pos_category, meaning)
    if cached is not None:
        return cached
    user = f"POS: {pos_category}\nGloss: {meaning}"
    result = parse_structured(_SYSTEM_EXTRACT, user, LookupLemmas, model="claude-haiku-4-5", max_tokens=512)
    lemmas = [l.strip().lower() for l in result.lemmas if l and l.strip()]
    # Dedupe preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for l in lemmas:
        if l not in seen:
            seen.add(l)
            out.append(l)
    _write_cache(pos_category, meaning, out)
    return out


def _collect_latin_anchors(definition: dict) -> list[str]:
    """Union of Latin from Definition.latin + SubSense.latin + Quotation.latin."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(s: str | None) -> None:
        if not s:
            return
        s = s.strip()
        if not s or s in seen:
            return
        seen.add(s)
        out.append(s)

    _add(definition.get("latin"))
    for q in definition.get("quotations") or []:
        _add(q.get("latin"))
    for ss in definition.get("sub_senses") or []:
        _add(ss.get("latin"))
        for q in ss.get("quotations") or []:
            _add(q.get("latin"))
    return out


def _collect_citations(definition: dict) -> list[str]:
    out: list[str] = []
    for q in definition.get("quotations") or []:
        c = (q.get("citations") or "").strip()
        if c:
            out.append(c)
    for ss in definition.get("sub_senses") or []:
        for q in ss.get("quotations") or []:
            c = (q.get("citations") or "").strip()
            if c:
                out.append(c)
    return out


def _bilingual_quotations(quotations: list[dict] | None) -> list[QuotationRef]:
    """Keep only quotations that have BOTH old_english and english so the
    reverse-dict reader gets a readable example. Latin is dropped here — the
    reverse entry doesn't need it beside the OE-English pairing."""
    out: list[QuotationRef] = []
    for q in quotations or []:
        oe = (q.get("old_english") or "").strip()
        en = (q.get("english") or "").strip()
        if not oe or not en:
            continue
        cite = (q.get("citations") or "").strip() or None
        out.append(QuotationRef(old_english=oe, english=en, citations=cite))
    return out


def _sense_path(def_label: str | None, sub_label: str | None = None) -> str:
    parts = [p for p in (def_label, sub_label) if p]
    return "".join(parts) or ""


def _iter_meaning_units(definition: dict):
    """Yield (meaning_text, sense_path, sibling_glosses, latin_anchors, citations,
    quotations) for the top-level Definition and each SubSense with a non-null
    meaning. Quotations are scoped to the level they appear at — the top-level
    yield gets Definition-level quotations only, SubSense yields get their own."""
    top_meaning = definition.get("meaning")
    top_label = definition.get("sense_label")
    if top_meaning:
        yield (
            top_meaning,
            _sense_path(top_label),
            [],
            _collect_latin_anchors(definition),
            _collect_citations(definition),
            _bilingual_quotations(definition.get("quotations")),
        )
    for ss in definition.get("sub_senses") or []:
        m = ss.get("meaning")
        if not m:
            continue
        latin: list[str] = []
        if ss.get("latin"):
            latin.append(ss["latin"])
        for q in ss.get("quotations") or []:
            if q.get("latin"):
                latin.append(q["latin"])
        cits = [
            (q.get("citations") or "").strip()
            for q in (ss.get("quotations") or [])
            if q.get("citations")
        ]
        yield (
            m,
            _sense_path(top_label, ss.get("label")),
            [top_meaning] if top_meaning else [],
            latin,
            cits,
            _bilingual_quotations(ss.get("quotations")),
        )


def _process_entry(entry: dict) -> list[GlossToken]:
    rows: list[GlossToken] = []
    oe_lemma = entry.get("citation_form")
    if not oe_lemma:
        return rows
    variants = list(entry.get("variant_forms") or [])
    for d in entry.get("definitions") or []:
        pos_obj = d.get("pos") or {}
        pos_cat = pos_obj.get("category")
        if pos_cat not in _ALLOWED_POS:
            continue
        gender = pos_obj.get("gender") if pos_cat == "noun" else None
        for meaning, path, siblings, latin, cits, quotes in _iter_meaning_units(d):
            lemmas = extract_lemmas(pos_cat, meaning)
            for lem in lemmas:
                rows.append(
                    GlossToken(
                        oe_lemma=oe_lemma,
                        pos=pos_cat,
                        gender=gender,
                        variants=variants,
                        english_token=lem,
                        sibling_glosses=siblings,
                        latin_anchors=latin,
                        citations=cits,
                        quotations=quotes,
                        sense_path=path,
                    )
                )
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--parsed-dir", default=str(_ROOT / "oe_dict" / "parsed_entries"))
    ap.add_argument("--out", default=str(_OUT_PATH))
    ap.add_argument("--limit", type=int, default=None, help="Process only the first N parsed entries (pilot).")
    args = ap.parse_args(argv)

    files = sorted(glob.glob(os.path.join(args.parsed_dir, "*.json")))
    if args.limit is not None:
        files = files[: args.limit]

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    n_rows = 0
    n_failures = 0
    with open(args.out, "w", encoding="utf-8") as f:
        for path in tqdm.tqdm(files, desc="extract"):
            try:
                with open(path, encoding="utf-8") as g:
                    entry = json.load(g)
            except (OSError, json.JSONDecodeError):
                continue
            try:
                rows = _process_entry(entry)
            except Exception as e:  # keep going on LLM/schema failure
                n_failures += 1
                tqdm.tqdm.write(f"[fail] {os.path.basename(path)}: {e}")
                continue
            for r in rows:
                f.write(r.model_dump_json() + "\n")
                n_rows += 1

    print(f"Wrote {n_rows} gloss-token rows to {args.out} ({n_failures} entries failed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
