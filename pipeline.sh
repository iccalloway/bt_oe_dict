#!/bin/bash
# End-to-end pipeline runner (everything except the final DDK compile).
#
# Stages run independently — pick one, several, or `all`. Each stage assumes
# the previous stage's outputs are already on disk; incremental caches
# (english_dict/cache/**) mean re-running is cheap after the first pass.
#
# Usage:
#   ./pipeline.sh <stage> [<stage> ...]
#   ./pipeline.sh all
#
# Stages:
#   parse           Parse resources/bt_text.txt → parsed/*.json (LLM, slow)
#   velar           Find OE citation forms with unresolved K/G. Writes
#                   oe_dict/velar_normalization/corrections.csv — you then edit
#                   column B to add hyphens forcing morpheme segmentation.
#   extract         Extract lookup-ready English lemmas from OE glosses (LLM)
#   candidates      WordNet synset lookup for each extracted lemma (no LLM)
#   disambiguate    Pick a synset per polysemous (OE, English) pair (LLM)
#   invert          Aggregate into English → OE entries, filter quotations
#   oe-xml          Render OE half → oe_templates/MyDictionary.oe.xml
#   en-xml          Render English half → oe_templates/MyDictionary.en.xml
#   merge           Concatenate both halves → oe_templates/MyDictionary.xml
#   all             parse → velar → extract → candidates → disambiguate →
#                   invert → oe-xml → en-xml → merge
#                   (velar leaves corrections.csv for manual review; the
#                    subsequent stages run against whatever is currently
#                    committed. Re-run `all` or `oe-xml` after editing it.)
#
# After merge, run ./compile.sh to build and install the .dictionary bundle.

set -euo pipefail
cd "$(dirname "$0")"

if [[ -f environment.env ]]; then
  # shellcheck source=/dev/null
  source environment.env
fi

_parse()        { echo "==> parse";        uv run oe_dict/parse.py; }
_velar()        { echo "==> velar";        uv run oe_dict/velar_normalization/find_ambiguous.py; }
_extract()      { echo "==> extract";      uv run english_dict/extract.py; }
_candidates()   { echo "==> candidates";   uv run english_dict/candidates.py; }
_disambiguate() { echo "==> disambiguate"; uv run english_dict/disambiguate.py; }
_invert()       { echo "==> invert";       uv run english_dict/invert.py; }
_oe_xml()       { echo "==> oe-xml";       uv run oe_dict/write_xml.py; }
_en_xml()       { echo "==> en-xml";       uv run english_dict/write_xml.py; }
_merge() {
  echo "==> merge"
  uv run oe_dict/merge_xml.py --out oe_templates/MyDictionary.xml \
    oe_templates/MyDictionary.oe.xml \
    oe_templates/MyDictionary.en.xml
}

_all() {
  _parse
  _velar
  _extract
  _candidates
  _disambiguate
  _invert
  _oe_xml
  _en_xml
  _merge
}

usage() {
  sed -n '2,/^set -euo pipefail/p' "$0" | sed 's/^# \{0,1\}//' | sed '/set -euo pipefail/d'
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

for stage in "$@"; do
  case "$stage" in
    parse)        _parse ;;
    velar)        _velar ;;
    extract)      _extract ;;
    candidates)   _candidates ;;
    disambiguate) _disambiguate ;;
    invert)       _invert ;;
    oe-xml)       _oe_xml ;;
    en-xml)       _en_xml ;;
    merge)        _merge ;;
    all)          _all ;;
    -h|--help|help) usage; exit 0 ;;
    *) echo "Unknown stage: $stage" >&2; usage; exit 1 ;;
  esac
done
