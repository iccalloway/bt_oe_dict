#!/bin/bash
# Regenerate the requested XML halves, merge them into MyDictionary.xml,
# then run DDK to compile and install the .dictionary bundle.
#
# Toggle the two halves via the flags below. Both default on.
#   LOAD_OE=1        include the Bosworth-Toller OE → English side
#   LOAD_ENGLISH=1   include the WordNet-disambiguated English → OE reverse side
# If both are 0, the script fails (nothing to build).

set -euo pipefail
cd "$(dirname "$0")"

LOAD_OE=${LOAD_OE:-1}
LOAD_ENGLISH=${LOAD_ENGLISH:-1}

XMLS=()

if [[ "$LOAD_OE" -eq 1 ]]; then
  echo "==> Regenerating OE XML"
  uv run oe_dict/write_xml.py
  XMLS+=("oe_templates/MyDictionary.oe.xml")
fi

if [[ "$LOAD_ENGLISH" -eq 1 ]]; then
  echo "==> Regenerating reverse (English) XML"
  uv run english_dict/write_xml.py
  XMLS+=("oe_templates/MyDictionary.en.xml")
fi

if [[ ${#XMLS[@]} -eq 0 ]]; then
  echo "Nothing to build: both LOAD_OE and LOAD_ENGLISH are 0." >&2
  exit 1
fi

echo "==> Merging: ${XMLS[*]}"
uv run oe_dict/merge_xml.py --out oe_templates/MyDictionary.xml "${XMLS[@]}"

echo "==> Compiling .dictionary"
cd oe_templates
make clean
make
make install
