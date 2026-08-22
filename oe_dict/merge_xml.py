"""Merge one or more DDK-format XML files into a single `<d:dictionary>`.

`src/write_xml.py` produces `oe_templates/MyDictionary.oe.xml` (OE → English)
and `rev_dict/write_xml.py` produces `oe_templates/MyDictionary.en.xml`
(English → OE). This script concatenates the `<d:entry>` children of any
given inputs into a single output XML that DDK can compile.

Preserves input order; does not attempt to dedupe entries by ID (each
writer is responsible for keeping its own IDs unique — and the two writers
use disjoint ID namespaces: OE entries use the citation form as-is,
English entries use the `en_` prefix).

Usage:
    uv run src/merge_xml.py --out oe_templates/MyDictionary.xml \\
        oe_templates/MyDictionary.oe.xml \\
        oe_templates/MyDictionary.en.xml
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.cElementTree as ET
from pathlib import Path


_D_NS = "http://www.apple.com/DTDs/DictionaryService-1.0.rng"
_DEFAULT_NS = "http://www.w3.org/1999/xhtml"


def _register_namespaces() -> None:
    ET.register_namespace("", _DEFAULT_NS)
    ET.register_namespace("d", _D_NS)


def merge(inputs: list[Path], out: Path) -> tuple[int, int]:
    _register_namespaces()
    template = Path(__file__).resolve().parent.parent / "resources" / "template.xml"
    out_tree = ET.parse(template)
    out_root = out_tree.getroot()

    n_files = 0
    n_entries = 0
    for path in inputs:
        if not path.exists():
            print(f"[warn] missing input, skipping: {path}", file=sys.stderr)
            continue
        n_files += 1
        tree = ET.parse(path)
        root = tree.getroot()
        for child in list(root):
            # child.tag is fully-qualified, e.g. '{...}entry' — copy verbatim.
            out_root.append(child)
            n_entries += 1

    out.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(out_tree, space="\t", level=0)
    with open(out, "wb") as g:
        out_tree.write(g, encoding="utf-8")
    return n_files, n_entries


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, help="Output merged XML path.")
    ap.add_argument("inputs", nargs="+", help="Input XML files to merge, in order.")
    args = ap.parse_args(argv)

    inputs = [Path(p) for p in args.inputs]
    n_files, n_entries = merge(inputs, Path(args.out))
    if n_files == 0:
        print("No input files were readable — nothing written.", file=sys.stderr)
        return 1
    print(f"Merged {n_entries} entries from {n_files} file(s) → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
