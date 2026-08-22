# bt-processing

Parse the Bosworth-Toller Anglo-Saxon Dictionary into structured JSON, then compile it into an installable Apple Dictionary bundle with both an Old English → English side and an English → Old English reverse side.

The source (`resources/bt_text.txt`) is a scanned, semi-structured plain-text dump of the printed dictionary — full of one-off abbreviations, embedded Latin, Roman-numeral senses, sub-sense brackets like `(1)(a)(α)`, supplement additions marked `Add:--`, OCR entities like `&a-long;` and `Æ-acute;`, and cross-references. It's not machine-parseable with regex. This pipeline hands each entry to Claude with a Pydantic-typed tool schema, writes one JSON per entry, then renders those JSONs into the XML format Apple's Dictionary Development Kit (DDK) compiles into a `.dictionary` bundle.

## Pipeline

```
resources/bt_text.txt
     │
     └─ oe_dict/parse.py ─► oe_dict/parsed_entries/*.json
                                    │
              ┌─────────────────────┼────────────────────────┐
              │                                              │
              ▼                                              ▼
      oe_dict/write_xml.py                    english_dict/{extract,candidates,
              │                               disambiguate,invert}.py
              │                                              │
              ▼                                              ▼
    oe_templates/MyDictionary.oe.xml          english_dict/parsed_entries/*.json
                              │                          │
                              │                          ▼
                              │              english_dict/write_xml.py
                              │                          │
                              │                          ▼
                              │            oe_templates/MyDictionary.en.xml
                              │                          │
                              └──── oe_dict/merge_xml.py ─┘
                                            │
                                            ▼
                              oe_templates/MyDictionary.xml
                                            │
                                            ▼
                                       compile.sh
                                            │
                                            ▼
                                 installed .dictionary
```

Run the whole thing (minus compile) with `./pipeline.sh all`, or pick individual stages: `./pipeline.sh <stage> [<stage> ...]`. See `./pipeline.sh help` for the stage list.

## Setup

```bash
uv sync                                    # install anthropic, pydantic, tqdm, nltk, eng-to-ipa
export ANTHROPIC_API_KEY=...               # or put it in environment.env

# One-time WordNet download (needed by english_dict/candidates.py + invert.py)
uv run python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
```

## Usage

```bash
./pipeline.sh parse             # LLM parse bt_text.txt → oe_dict/parsed_entries/*.json
./pipeline.sh velar             # then hand-edit oe_dict/velar_normalization/corrections.csv
./pipeline.sh extract           # english lemmas from OE glosses (Haiku)
./pipeline.sh candidates        # WordNet synset lookup
./pipeline.sh disambiguate      # Sonnet picks best synset for polysemous lemmas
./pipeline.sh invert            # aggregate → english_dict/parsed_entries/{lemma}.{pos}.json
./pipeline.sh oe-xml en-xml merge
./compile.sh                    # DDK build + install
```

Open Dictionary.app → Preferences → enable "An Anglo-Saxon Dictionary" in the source list.

## Old English → English side (`oe_dict/`)

- **`parse.py`** splits `resources/bt_text.txt` on blank lines and iterates. Each entry is sent to Claude via `parse_structured` (in `llm.py`) with `EntryBatch` (from `schema.py`) as a forced tool call — the response is guaranteed to validate against the schema. `source_text` is stored on each output record so re-runs skip already-parsed entries. The system prompt is prompt-cached, so tool schema + instructions are billed at 10% after the first entry.
- **`write_xml.py`** reads every JSON in `oe_dict/parsed_entries/`, normalizes text (acute→macron, OCR entity substitution, ligature handling), and emits one `<d:entry>` per JSON into `oe_templates/MyDictionary.oe.xml`. Groups definitions by POS, renders Roman-numeral senses, nested `(1)/(a)/(α)` sub-senses, quotations (OE + Latin + English + citation), and cross-references as clickable `x-dictionary:r:` anchors. Deduplicates entry IDs and alias indexes globally.
- **`phonology.py`** — Old English → IPA transcriber (diphthongs, palatalization, morpheme overrides).
- **`velar_normalization/find_ambiguous.py`** lists citation forms whose transcription still contains unresolved K/G and writes `corrections.csv` for hand-editing. Add hyphens in column B (e.g. `þeōdendlīc → þeōdend-līc`) to expose morpheme boundaries so `morphemes.json` fires. `write_xml.py` uses the corrected form and preserves the original as a search alias.
- **`merge_xml.py`** concatenates the OE and English halves into a single `<d:dictionary>` for DDK.

## English → Old English side (`english_dict/`)

Inverts `oe_dict/parsed_entries/*.json` into a sense-disambiguated lookup: given a Modern English word, list the Old English lemmas that mean it, grouped by WordNet synset. Read-only against `parsed_entries/`.

Four stages, each writes an intermediate JSONL that the next stage reads:

1. **`extract.py`** — Haiku pulls dictionary-form English lemmas from BT glosses. Only equivalence-y lemmas (not description words). Cache: `english_dict/cache/extract/`.
2. **`candidates.py`** — `nltk.corpus.wordnet` lookup per (english_lemma, POS). 0 → `unmapped`, 1 → auto-resolve, ≥2 → queue for Phase 3.
3. **`disambiguate.py`** — Sonnet picks the best synset for polysemous rows using OE co-text and Latin anchors. Cache: `english_dict/cache/disambiguate/`.
4. **`invert.py`** — aggregates by `(english_lemma, synset_id)`, filters bilingual quotations so they only appear on entries whose headword lemma actually shows up in the English translation (lemmatized comparison via WordNet), and writes one JSON per (english_lemma, pos) into `english_dict/parsed_entries/`.

Then `english_dict/write_xml.py` renders those into `oe_templates/MyDictionary.en.xml`, including IPA pronunciations via `eng-to-ipa`.

Nouns and verbs only in the first pass (best WordNet coverage). Rows whose lemma isn't in WordNet land under `historical_unmapped` in the final output rather than being dropped.

## Layout

| Path | Role |
|---|---|
| `resources/bt_text.txt` | Source dump (not tracked in git) |
| `resources/template.xml` | Empty `<d:dictionary>` scaffold |
| `pipeline.sh` | Named-stage runner (`parse`, `velar`, `extract`, …, `merge`, `all`) |
| `compile.sh` | `make clean && make && make install` in `oe_templates/` |
| `oe_dict/schema.py` | Pydantic models — `EntryBatch`, `OldEnglishEntry`, `Definition`, `SubSense`, POS variants (incl. `AffixPOS`), `Quotation` |
| `oe_dict/llm.py` | Thin wrapper around `anthropic.messages.create` with forced tool call + prompt caching |
| `oe_dict/parse.py` | LLM parsing loop with skip-if-already-parsed, merge-on-collision, failure collection |
| `oe_dict/phonology.py` | Old English → IPA transcriber |
| `oe_dict/write_xml.py` | JSON → Apple Dictionary XML renderer (OE side) |
| `oe_dict/merge_xml.py` | Concatenate OE + English XML halves into one `<d:dictionary>` |
| `oe_dict/velar_normalization/morphemes.json` | Whole-morpheme phoneme overrides for ambiguous ⟨c⟩/⟨g⟩ |
| `oe_dict/velar_normalization/find_ambiguous.py` | Lists unresolved K/G words, writes `corrections.csv` |
| `oe_dict/velar_normalization/corrections.csv` | Hand-edited citation-form corrections (adds hyphens to expose morphemes) |
| `oe_dict/parsed_entries/` | One JSON per parsed OE entry, keyed by citation form |
| `english_dict/schema.py` | Pydantic models for the reverse pipeline (`LookupLemmas`, `Disambiguation`, `QuotationRef`, intermediate row types) |
| `english_dict/extract.py` | Phase 1 — LLM extracts English lemmas from BT glosses |
| `english_dict/candidates.py` | Phase 2 — WordNet lookup, monosemy fast-path |
| `english_dict/disambiguate.py` | Phase 3 — LLM picks the best synset for polysemous lemmas |
| `english_dict/invert.py` | Phase 4 — aggregate + lemmatize-filter quotations |
| `english_dict/write_xml.py` | JSON → Apple Dictionary XML renderer (English side, with IPA) |
| `english_dict/cache/` | Per-key JSON cache for the two LLM stages (safe to delete) |
| `english_dict/parsed_entries/` | Final reverse-dictionary JSONs, one per (english_lemma, pos) |
| `oe_templates/` | DDK project (Makefile, `MyDictionary.css`, `MyInfo.plist`); receives the generated XML |

## Notes

- `parse.py` defaults to `limit=1000` per run (see `read_entries`). Set to `None` for a full pass.
- Parse failures are collected and printed at the end of the run rather than aborting.
- Normalization decisions (acute→macron, `Æ-acute;` → `Ǣ`, `þ-bar` → `ꝥ`, etc.) live in `oe_dict/write_xml.normalize`.
- Scripts resolve paths via `Path(__file__).parent[.parent]`, so they can be invoked from any working directory.
- All LLM calls are cached under `english_dict/cache/` — re-runs after a prompt tweak only re-hit rows whose inputs actually changed. Bump the `_PROMPT_VERSION` constant in `extract.py` to force cache misses across a prompt change.
