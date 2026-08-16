import glob
import json
import os
import re
import unicodedata
import xml.etree.cElementTree as ET

from phonology import transcribe


tree = ET.parse("template.xml")
ET.register_namespace("", "http://www.w3.org/1999/xhtml")
ET.register_namespace("d", "http://www.apple.com/DTDs/DictionaryService-1.0.rng")
root = tree.getroot()

gender_d = {"m": "masculine", "f": "feminine", "n": "neuter"}
_NUMBER_ABBR = {"singular": "sg", "plural": "pl", "dual": "du"}
_TENSE_GROUPS = [
    ("present", {"present"}),
    ("past", {"preterite"}),
    ("participle", {"past participle", "present participle"}),
    ("imperative", {"imperative"}),
    ("infinitive", {"infinitive"}),
]


def _verb_form_label(f):
    parts = []
    if f.get("person") and f.get("number"):
        parts.append(f"{f['person']}{_NUMBER_ABBR.get(f['number'], f['number'])}")
    elif f.get("number"):
        parts.append(_NUMBER_ABBR.get(f["number"], f["number"]))
    if f.get("tense") in {"past participle", "present participle"}:
        parts.insert(0, f["tense"])
    return " ".join(parts) or "form"


def _group_verb_forms(forms):
    groups = []
    for label, tenses in _TENSE_GROUPS:
        members = [f for f in forms if f.get("tense") in tenses]
        if members:
            groups.append((label, members))
    return groups

_ACUTE_TO_MACRON = str.maketrans({
    "á": "ā", "é": "ē", "í": "ī", "ó": "ō", "ú": "ū", "ǽ": "ǣ", "ý": "ȳ",
    "Á": "Ā", "É": "Ē", "Í": "Ī", "Ó": "Ō", "Ú": "Ū", "Ǽ": "Ǣ", "Ý": "Ȳ",
})
_A_PREFIX = re.compile(r"\b([aA])-")

# OCR entities like `&a-long;`, `Æ-acute;`, `þ-bar;` — sometimes with `&` prefix,
# sometimes without. Mapped to a single Unicode codepoint each.
_ENTITY_MAP = {
    # long → macron
    "a-long": "ā", "e-long": "ē", "i-long": "ī", "o-long": "ō", "u-long": "ū", "y-long": "ȳ",
    "A-long": "Ā", "E-long": "Ē", "I-long": "Ī", "O-long": "Ō", "U-long": "Ū", "Y-long": "Ȳ",
    "æ-long": "ǣ", "Æ-long": "Ǣ",
    # acute → macron (BT convention: acute marks length)
    "a-acute": "ā", "e-acute": "ē", "i-acute": "ī", "o-acute": "ō", "u-acute": "ū", "y-acute": "ȳ",
    "A-acute": "Ā", "E-acute": "Ē", "I-acute": "Ī", "O-acute": "Ō", "U-acute": "Ū", "Y-acute": "Ȳ",
    "æ-acute": "ǣ", "Æ-acute": "Ǣ",
    # short → breve
    "a-short": "ă", "e-short": "ĕ", "i-short": "ĭ", "o-short": "ŏ", "u-short": "ŭ",
    "A-short": "Ă", "E-short": "Ĕ", "I-short": "Ĭ", "O-short": "Ŏ", "U-short": "Ŭ",
    # bar/stroke
    "þ-bar": "ꝥ", "Þ-bar": "Ꝥ",
    "d-bar": "đ", "D-bar": "Đ",
    "l-bar": "ł", "L-bar": "Ł",
    "b-bar": "ƀ", "B-bar": "Ƀ",
    "t-bar": "ŧ", "T-bar": "Ŧ",
    # hook → ogonek
    "e-hook": "ę", "E-hook": "Ę",
    "a-hook": "ą", "A-hook": "Ą",
}
# Match single-letter entities (including ligatures) with optional `&` prefix.
# Single-char anchor prevents greedy matches like "DÆ-acute" swallowing the D.
_LETTER_ENTITY_RE = re.compile(r"&?([A-Za-zÆæÐðÞþŒœ])-([a-z]+);")


def _replace_letter_entity(m):
    key = f"{m.group(1)}-{m.group(2)}"
    return _ENTITY_MAP.get(key, m.group(0))


def normalize(text):
    if not text:
        return text
    text = _LETTER_ENTITY_RE.sub(_replace_letter_entity, text)
    text = text.replace("&dash-uncertain;", "—")
    text = text.translate(_ACUTE_TO_MACRON)
    return _A_PREFIX.sub(lambda m: "Ā" if m.group(1) == "A" else "ā", text)


_LIGATURE_EXPANSION = str.maketrans({
    "æ": "ae", "Æ": "AE",
    "œ": "oe", "Œ": "OE",
    "þ": "th", "Þ": "TH",
    "ð": "d", "Ð": "D",
    "ƿ": "w", "Ƿ": "W",
    "ꝥ": "th", "Ꝥ": "TH",
})


def strip_diacritics(text):
    if not text:
        return text
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if not unicodedata.combining(c))


def searchable_alias(text):
    """Compiler-friendly search key: strip diacritics and expand ligatures.

    Apple Dictionary's search index normalizes headwords by lowercasing,
    stripping combining marks, and expanding ligatures. Emitting the alias
    already in that form avoids per-entry duplicates the compiler would
    otherwise skip and warn about.
    """
    return strip_diacritics(text).translate(_LIGATURE_EXPANSION)


_PRON_WORD_RE = re.compile(r"[A-Za-zĀāǢǣĒēĪīŌōŪūȲȳÆæÐðÞþŒœȦȧĊċĠġŚś\-]+")


def _pronunciation(citation: str) -> str:
    """Best-effort IPA-flavored transcription of the citation headword.

    Multi-word or comma-separated citations get each word transcribed and
    joined with `, `. Words with characters `transcribe` can't tokenize (or
    that raise) are silently dropped so a single odd headword doesn't kill
    the whole line."""
    if not citation:
        return ""
    parts: list[str] = []
    for word in _PRON_WORD_RE.findall(citation):
        try:
            p = transcribe(word)
        except Exception:
            continue
        if not p:
            continue
        # Morpheme boundaries have no place in a pronunciation. Where the
        # syllabifier already left a syllable break at the hyphen, `-` → `.`
        # keeps it; where the break would collapse (adjacent to another `.`
        # or at a word edge), the cleanup below absorbs it so the flanking
        # segments merge into their natural syllable.
        p = p.replace("-", ".")
        while ".." in p:
            p = p.replace("..", ".")
        p = p.strip(".")
        if p:
            parts.append(p)
    return ", ".join(parts)


def _render_quotations(parent, quotations):
    # Require an Old English line — quotations without OE are usually just Latin
    # source material or citation fragments that add little without the OE text.
    kept = [q for q in (quotations or []) if normalize(q.get("old_english"))]
    if not kept:
        return
    ul = ET.SubElement(parent, "ul")
    ul.attrib["class"] = "quotes"
    for q in kept:
        line_specs = [
            ("q-en", normalize(q.get("english"))),
            ("q-la", normalize(q.get("latin"))),
            ("q-oe", normalize(q.get("old_english"))),
        ]
        lines = [(cls, text) for cls, text in line_specs if text]
        li = ET.SubElement(ul, "li")
        for cls, text in lines:
            span = ET.SubElement(li, "span")
            span.attrib["class"] = cls
            span.text = text
        cite = normalize(q.get("citations"))
        if cite:
            cite_span = ET.SubElement(li, "span")
            cite_span.attrib["class"] = "q-cite"
            cite_span.text = f" ({cite})"


def _render_sense_body(li, sense, heading=None):
    label_text = sense.get("sense_label") or sense.get("label")
    has_meaning_line = bool(label_text or heading or sense.get("meaning") or sense.get("latin"))
    if has_meaning_line:
        meaning = ET.SubElement(li, "p")
        if label_text:
            label = ET.SubElement(meaning, "span")
            label.attrib["class"] = "sense-label"
            label.text = label_text
        if heading:
            h = ET.SubElement(meaning, "span")
            h.attrib["class"] = "sub-heading"
            h.text = heading
        if sense.get("meaning"):
            en = ET.SubElement(meaning, "span")
            en.attrib["class"] = "meaning-en"
            en.text = normalize(sense["meaning"])
        if sense.get("latin"):
            la = ET.SubElement(meaning, "span")
            la.attrib["class"] = "meaning-la"
            la.text = f" (Lat. {normalize(sense['latin'])})"
    _render_quotations(li, sense.get("quotations", []))
    if sense.get("sub_senses"):
        sub_ol = ET.SubElement(li, "ol")
        sub_ol.attrib["class"] = "sub-senses"
        for sub in sense["sub_senses"]:
            sub_li = ET.SubElement(sub_ol, "li")
            _render_sense_body(sub_li, sub, heading=sub.get("heading"))


def _quotation_has_content(q):
    return any(q.get(k) for k in ("old_english", "english", "latin"))


def _sense_has_content(sense):
    if sense.get("meaning") or sense.get("latin"):
        return True
    if any(_sense_has_content(sub) for sub in sense.get("sub_senses", [])):
        return True
    if any(_quotation_has_content(q) and q.get("old_english") for q in sense.get("quotations", [])):
        return True
    pos = sense.get("pos", {})
    if pos.get("endings") or pos.get("forms") or pos.get("governs"):
        return True
    return False


def _sense_has_annotation(sense):
    """True when this sense needs a numbered <li> (meaning/label/sub-structure)."""
    return bool(
        sense.get("meaning")
        or sense.get("latin")
        or sense.get("sense_label")
        or sense.get("label")
        or sense.get("sub_senses")
    )


def create_entry(d, seen_aliases: set[str] | None = None):
    # Skip entries with no useful content — nothing but a headword to render.
    has_defs = any(_sense_has_content(defn) for defn in d.get("definitions", []))
    if not has_defs and not d.get("cross_references"):
        return None

    if seen_aliases is None:
        seen_aliases = set()

    citation = normalize(d["citation_form"])
    entry = ET.Element("d:entry")
    entry.attrib["id"] = citation
    entry.attrib["d:title"] = citation

    display = ET.SubElement(entry, "d:index")
    display.attrib["d:value"] = citation

    # The DDK compiler auto-normalizes each d:index value (lowercase, strip
    # diacritics, expand ligatures like æ→ae, þ→th) to build its search key,
    # so we only need to emit the human-readable macronized forms — typing
    # `arfaestnes` will still find `ārfæstnes`. Emitting a pre-normalized
    # alias too just collides with the compiler-generated key and produces
    # "Duplicate index. Skipped" warnings.
    seen = {citation}
    for v in d.get("variant_forms", []):
        form = normalize(v)
        if not form or form in seen:
            continue
        key = form.lower()
        if key in seen_aliases:
            continue
        seen.add(form)
        seen_aliases.add(key)
        alias = ET.SubElement(entry, "d:index")
        alias.attrib["d:value"] = form
        alias.attrib["d:title"] = citation

    body = ET.SubElement(entry, "body")
    title = ET.SubElement(body, "h1")
    title.text = citation
    pron = _pronunciation(citation)
    if pron:
        pron_span = ET.SubElement(title, "span")
        pron_span.attrib["class"] = "pron"
        pron_span.text = f" | {pron} |"

    # Group definitions by rendered POS category, preserving first-seen order.
    groups = {}  # cat -> list[definition]
    for definition in d["definitions"]:
        if not _sense_has_content(definition):
            continue
        cat = definition["pos"]["category"]
        if cat == "noun" and definition["pos"].get("gender"):
            cat = f"{gender_d[definition['pos']['gender']]} noun"
        elif cat == "preposition" and definition["pos"].get("governs"):
            cat = f"preposition (w. {', '.join(definition['pos']['governs'])})"
        groups.setdefault(cat, []).append(definition)

    for cat, defs in groups.items():
        div = ET.SubElement(body, "div")
        ET.SubElement(ET.SubElement(div, "p"), "b").text = cat

        first = defs[0]
        if cat.endswith("noun") and first["pos"].get("endings"):
            case_examples = ", ".join(
                f"{ending['case']} {_NUMBER_ABBR.get(ending['number'], ending['number'])}: -{normalize(ending['ending'])}"
                for ending in first["pos"]["endings"]
            )
            ET.SubElement(
                ET.SubElement(div, "p"), "b", {"class": "ending"}
            ).text = case_examples

        if cat == "verb" and first["pos"].get("forms"):
            for label, members in _group_verb_forms(first["pos"]["forms"]):
                parts = ", ".join(
                    f"{_verb_form_label(f)}: -{normalize(f['form']).lstrip('-')}"
                    for f in members
                )
                ET.SubElement(
                    ET.SubElement(div, "p"), "b", {"class": "ending"}
                ).text = f"{label}: {parts}"

        if any(_sense_has_annotation(defn) for defn in defs):
            ol = ET.SubElement(body, "ol")
            for definition in defs:
                li = ET.SubElement(ol, "li")
                _render_sense_body(li, definition)
        else:
            # Pure-quotation group — no gloss, no labels; render quotations flat
            # under the POS header without an <ol> so we don't emit "1." numbering.
            for definition in defs:
                _render_quotations(div, definition.get("quotations", []))

    # If any list has custom sense labels (I., II., ...) drop the auto-numbering
    # to avoid "1. I. ..." duplicates. We do this post-hoc so the decision is
    # per-list and doesn't require pre-scanning definitions.
    for ol in body.iter("ol"):
        if any(li.find("p/span[@class='sense-label']") is not None for li in ol.findall("li")):
            existing = ol.attrib.get("class", "")
            ol.attrib["class"] = (existing + " labeled").strip()

    if d.get("cross_references"):
        xref = ET.SubElement(body, "p")
        xref.attrib["class"] = "xref"
        xref.text = "See also: "
        refs = d["cross_references"]
        for i, ref in enumerate(refs):
            target = normalize(ref)
            a = ET.SubElement(xref, "a")
            a.attrib["href"] = f"x-dictionary:r:{target}"
            a.attrib["class"] = "xref-target"
            a.text = target
            if i < len(refs) - 1:
                a.tail = ", "

    return entry


if __name__ == "__main__":
    seen_aliases: set[str] = set()
    for file in glob.glob(os.path.join("./parsed/", "*.json")):
        with open(file, "r", encoding="utf-8") as f:
            d = json.load(f)
            entry = create_entry(d, seen_aliases)
            if entry is not None:
                root.append(entry)

    with open("./oe_templates/MyDictionary.xml", "wb") as g:
        ET.indent(tree, space="\t", level=0)
        tree.write(g, encoding="utf-8")
