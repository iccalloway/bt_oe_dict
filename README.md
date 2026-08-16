# bt-processing

Parse the Bosworth-Toller Anglo-Saxon Dictionary into structured JSON, then compile it into an installable Apple Dictionary bundle.

The source (`bt_text.txt`) is a scanned, semi-structured plain-text dump of the printed dictionary — full of one-off abbreviations, embedded Latin, Roman-numeral senses, sub-sense brackets like `(1)(a)(α)`, supplement additions marked `Add:--`, OCR entities like `&a-long;` and `Æ-acute;`, and cross-references. It's not machine-parseable with regex. This pipeline hands each entry to Claude with a Pydantic-typed tool schema, writes one JSON file per entry, and then renders those JSONs into the XML format Apple's Dictionary Development Kit (DDK) compiles into a `.dictionary` bundle.

## Pipeline

```
bt_text.txt  ──parse.py──►  parsed/*.json  ──write_xml.py──►  oe_templates/MyDictionary.xml  ──compile.sh──►  installed .dictionary
```

### 1. Parse — `parse.py` + `llm.py` + `schema.py`

- `parse.py` splits `bt_text.txt` on blank lines, shuffles, and iterates entries.
- Each entry is sent to Claude via `parse_structured` (in `llm.py`) with `EntryBatch` (from `schema.py`) as a forced tool call — the response is guaranteed to validate against the schema.
- Output is one JSON file per entry in `parsed/`, keyed by citation form. `source_text` is stored on each record so re-runs skip already-parsed entries.
- The system prompt is prompt-cached (`cache_control: ephemeral`), so tool schema + instructions are billed at 10% after the first entry in a run.

### 2. Render — `write_xml.py`

- Reads every JSON in `parsed/`, normalizes text (acute→macron, OCR entity substitution, ligature handling), and emits one `<d:entry>` per JSON into `oe_templates/MyDictionary.xml`.
- Groups definitions by part of speech, renders Roman-numeral senses, nested `(1)/(a)/(α)` sub-senses, quotations (OE + Latin + English + citation), and cross-references as clickable `x-dictionary:r:` anchors.
- Skips empty entries and quotations without Old English text.
- Deduplicates alias indexes globally to avoid DDK "Duplicate index. Skipped" warnings.

### 3. Compile — `compile.sh`

- Wraps `make clean && make && make install` in `oe_templates/`, which invokes DDK's build tooling to produce the `.dictionary` bundle and drop it into `~/Library/Dictionaries/`.
- Requires Apple's [Dictionary Development Kit](https://developer.apple.com/download/all/?q=dictionary%20development%20kit) installed at the path referenced by `oe_templates/Makefile`.

## Setup

```bash
uv sync                                    # install anthropic, pydantic, tqdm
export ANTHROPIC_API_KEY=...               # or put it in environment.env
```

## Usage

```bash
uv run parse.py                            # populate parsed/ (skips existing)
uv run write_xml.py                        # regenerate oe_templates/MyDictionary.xml
./compile.sh                               # compile and install the .dictionary
```

Open Dictionary.app → Preferences → enable "Bosworth-Toller" in the source list.

## Layout

| File | Role |
|---|---|
| `bt_text.txt` | Source dump (not tracked in git) |
| `schema.py` | Pydantic models — `EntryBatch`, `OldEnglishEntry`, `Definition`, `SubSense`, POS variants, `Quotation` |
| `llm.py` | Thin wrapper around `anthropic.messages.create` with forced tool call + prompt caching |
| `parse.py` | LLM parsing loop with skip-if-already-parsed and failure collection |
| `write_xml.py` | JSON → Apple Dictionary XML renderer |
| `template.xml` | Empty `<d:dictionary>` scaffold that `write_xml.py` populates |
| `oe_templates/` | DDK project (Makefile, `MyDictionary.css`, `MyInfo.plist`) |
| `compile.sh` | `make clean && make && make install` |
| `parsed/` | One JSON per parsed entry, keyed by citation form |

## Notes

- The parse defaults to `limit=1000` per run (see `read_entries` in `parse.py`). Set to `None` for a full pass.
- Parse failures are collected and printed at the end of the run rather than aborting.
- Normalization decisions (acute→macron, `Æ-acute;` → `Ǣ`, `þ-bar` → `ꝥ`, etc.) live in `write_xml.normalize`.
