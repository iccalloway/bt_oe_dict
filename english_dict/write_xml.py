"""Render `english_dict/parsed_entries/*.json` into an Apple Dictionary XML fragment.

Produces one `<d:entry>` per (english_lemma, POS), grouped by WordNet synset.
Each OE equivalent is linked back to its OE entry via `x-dictionary:r:`, so
users can click through from the English side to the full Bosworth-Toller
entry on the OE side.

Output: `oe_templates/MyDictionary.en.xml`. Combine with the OE XML
(`MyDictionary.oe.xml`) via `oe_dict/merge_xml.py` before compiling with DDK.

Usage (from project root):
    uv run rev_dict/write_xml.py
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import warnings
import xml.etree.cElementTree as ET
from pathlib import Path

# eng-to-ipa's module ships with `\d` regexes that trigger a SyntaxWarning
# per import site. Silence at load time — nothing to fix upstream on our end.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", SyntaxWarning)
    import eng_to_ipa as _ipa  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(_ROOT / "oe_dict"))

# Load `oe_dict/write_xml.py` under an aliased name so it doesn't collide with
# this script's own module name (`write_xml`). We only need two helpers
# from it — `normalize` and `_apply_corrections` — to keep our OE
# cross-reference targets identical to the OE writer's primary d:index.
import importlib.util as _iu  # noqa: E402

_oe_spec = _iu.spec_from_file_location("_oe_write_xml", _ROOT / "oe_dict" / "write_xml.py")
_oe_wx = _iu.module_from_spec(_oe_spec)
_oe_spec.loader.exec_module(_oe_wx)
normalize = _oe_wx.normalize
_apply_corrections = _oe_wx._apply_corrections

from schema import ReverseEntry  # noqa: E402


_IN_DIR = Path(__file__).parent / "parsed_entries"
_OUT_PATH = _ROOT / "oe_templates" / "MyDictionary.en.xml"

_POS_LABEL = {"noun": "noun", "verb": "verb", "adjective": "adjective", "adverb": "adverb"}


def _register_namespaces() -> None:
    ET.register_namespace("", "http://www.w3.org/1999/xhtml")
    ET.register_namespace("d", "http://www.apple.com/DTDs/DictionaryService-1.0.rng")


def _oe_link_target(oe_lemma: str) -> str:
    """Return the OE citation form as it appears in `d:value` on its entry,
    so `x-dictionary:r:{target}` resolves correctly."""
    return _apply_corrections(normalize(oe_lemma) or "")


def _entry_id(english_lemma: str, pos: str) -> str:
    slug = "".join(ch if ch.isalnum() else "_" for ch in english_lemma).lower()
    return f"en_{slug}_{pos}"


def _ipa_for(english_lemma: str) -> str | None:
    """IPA transcription via CMU dict. Returns None if any token is OOV
    (eng-to-ipa marks unknowns with a trailing `*`), so we don't render
    half-transcribed multi-word headwords like `young mæn*`."""
    try:
        ipa = _ipa.convert(english_lemma).strip()
    except Exception:
        return None
    if not ipa or "*" in ipa:
        return None
    return ipa


def create_entry(entry: ReverseEntry, seen_ids: set[str]) -> ET.Element | None:
    if not entry.senses:
        return None

    ent = ET.Element("d:entry")
    entry_id = _entry_id(entry.english_lemma, entry.pos)
    # Guard against duplicate IDs across (english_lemma, pos) slug collisions.
    base = entry_id
    n = 2
    while entry_id in seen_ids:
        entry_id = f"{base}_{n}"
        n += 1
    seen_ids.add(entry_id)

    ent.attrib["id"] = entry_id
    ent.attrib["d:title"] = entry.english_lemma

    # Primary index: the English lemma. Dictionary.app displays d:value when
    # d:title is absent, so no title attribute needed — homographs (English
    # "bear" vs OE "bera") stay disambiguated by the different d:value spelling.
    idx = ET.SubElement(ent, "d:index")
    idx.attrib["d:value"] = entry.english_lemma

    body = ET.SubElement(ent, "body")
    h1 = ET.SubElement(body, "h1")
    h1.text = entry.english_lemma
    ipa = _ipa_for(entry.english_lemma)
    if ipa:
        pron = ET.SubElement(h1, "span")
        pron.attrib["class"] = "pron"
        pron.text = f" | {ipa} |"

    # POS on its own line below the headword, spelled out.
    pos_p = ET.SubElement(body, "p")
    pos_p.attrib["class"] = "pos"
    pos_p.text = _POS_LABEL.get(entry.pos, entry.pos)

    # No "labeled" class — we want the default decimal numbering + indent now
    # that per-<li> synset labels are gone.
    ol = ET.SubElement(body, "ol")
    ol.attrib["class"] = "en-senses"

    for sense in entry.senses:
        li = ET.SubElement(ol, "li")
        if sense.definition:
            gloss = ET.SubElement(li, "i")
            gloss.text = sense.definition

        equivs = ET.SubElement(li, "ul")
        equivs.attrib["class"] = "en-equivs"
        for eq in sense.oe_equivalents:
            eq_li = ET.SubElement(equivs, "li")
            target = _oe_link_target(eq.oe_lemma)
            a = ET.SubElement(eq_li, "a")
            a.attrib["href"] = f"x-dictionary:r:{target}" if target else "#"
            a.attrib["class"] = "xref-target"
            a.text = target or eq.oe_lemma
            if eq.gender:
                g = ET.SubElement(eq_li, "i")
                g.text = f" {eq.gender}."
            if eq.variants:
                var = ET.SubElement(eq_li, "span")
                var.attrib["class"] = "ending"
                var.text = " (" + ", ".join(eq.variants) + ")"
            if eq.latin_glosses:
                # Just the first Latin gloss — a compact anchor, not a full list.
                lat = ET.SubElement(eq_li, "span")
                lat.attrib["class"] = "meaning-la"
                lat.text = " · " + eq.latin_glosses[0]
            # Bilingual quotations (OE + English). Cap at 3 per equivalent so
            # a chatty entry doesn't dominate the reverse view.
            if eq.quotations:
                q_ul = ET.SubElement(eq_li, "ul")
                q_ul.attrib["class"] = "quotes"
                for q in eq.quotations[:3]:
                    q_li = ET.SubElement(q_ul, "li")
                    oe_span = ET.SubElement(q_li, "span")
                    oe_span.attrib["class"] = "q-oe"
                    oe_span.text = q.old_english
                    en_span = ET.SubElement(q_li, "span")
                    en_span.attrib["class"] = "q-en"
                    en_span.text = q.english
                    if q.citations:
                        c_span = ET.SubElement(q_li, "span")
                        c_span.attrib["class"] = "q-cite"
                        c_span.text = f" ({q.citations})"
    return ent


def build_tree() -> ET.ElementTree:
    _register_namespaces()
    tree = ET.parse(_ROOT / "resources" / "template.xml")
    root = tree.getroot()

    files = sorted(glob.glob(os.path.join(str(_IN_DIR), "*.json")))
    seen_ids: set[str] = set()
    n_written = 0
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        try:
            entry = ReverseEntry.model_validate(data)
        except Exception as e:
            print(f"[skip] {os.path.basename(path)}: {e}", file=sys.stderr)
            continue
        el = create_entry(entry, seen_ids)
        if el is not None:
            root.append(el)
            n_written += 1
    print(f"Wrote {n_written} reverse-dict entries.")
    return tree


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(_OUT_PATH))
    args = ap.parse_args(argv)

    tree = build_tree()
    ET.indent(tree, space="\t", level=0)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "wb") as g:
        tree.write(g, encoding="utf-8")
    print(f"Reverse-dict XML → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
