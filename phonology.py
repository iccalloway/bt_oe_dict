"""Old English orthography → phonological transcription with syllable breaks.

`transcribe(word)` takes a standard editorial Old English form (macrons for
long vowels, dot-above for palatal ċ/ġ/sċ) and returns a segment-and-syllable
transcription in an IPA-flavored notation, e.g.

    transcribe("bannan")     # → "bɑn.nɑn"
    transcribe("cniht")      # → "kniçt"
    transcribe("eorðe")      # → "eor.ðe"
    transcribe("hlūd")       # → "hluːd"
    transcribe("dæġ")        # → "dæj"
    transcribe("weċġ")       # → "wejj"
    transcribe("hūsian")     # → "huː.zi.ɑn"

Unmarked ⟨c⟩ / ⟨g⟩ in environments where the palatal/velar contrast cannot
be resolved from spelling alone (adjacent to a front vowel) are emitted as
capital ⟨K⟩ / ⟨G⟩ so a downstream lemma list can disambiguate them. `sc` and
`cg` are defaulted to /ʃ/ and /jj/ (the overwhelming majority realizations);
lexical exceptions with velar /sk/, /gg/ are not currently detected.

Stress is not marked — determining stress requires prefix/compound detection.
Hyphens in the input are treated as morpheme boundaries and preserved in the
output. Adding hyphens to compound or prefixed forms improves segmentation
(e.g. `ġe-hālgian` correctly renders the medial ⟨h⟩ as [h] rather than [ç]).
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path


# ── Vowels ────────────────────────────────────────────────────────────────

# Diphthongs stay as single phoneme strings so the syllabifier treats them as
# one nucleus. Long forms are listed first so longest-match tokenization picks
# them over their short + macronless prefix.
# U+035C COMBINING DOUBLE BREVE BELOW ( ͜ ) is the IPA tie linking the two
# vowel qualities of a diphthong (as in ⟨u͜i⟩); length is marked with a
# trailing ː on long diphthongs, matching the convention for long monophthongs.
_DIPHTHONGS: dict[str, str] = {
    "ēa": "æ\u035Cɑː", "ēo": "e\u035Coː", "īe": "i\u035Cyː", "īo": "i\u035Coː",
    # BT sometimes marks length on the second vowel of a long diphthong.
    "eā": "æ\u035Cɑː", "eō": "e\u035Coː", "iē": "i\u035Cyː", "iō": "i\u035Coː",
    "ea": "æ\u035Cɑ",  "eo": "e\u035Co",  "ie": "i\u035Cy",  "io": "i\u035Co",
}

_MONOPHTHONGS: dict[str, str] = {
    "ā": "ɑː", "ǣ": "æː", "ē": "eː", "ī": "iː",
    "ō": "oː", "ū": "uː", "ȳ": "yː",
    "a": "ɑ", "æ": "æ", "e": "e", "i": "i",
    "o": "o", "u": "u", "y": "y",
}

# Any orthographic vowel token that counts as "front" for palatalization
# decisions on adjacent unmarked ⟨c⟩ / ⟨g⟩.
_FRONT_VOWEL_KEYS: set[str] = {
    "i", "ī", "e", "ē", "y", "ȳ", "æ", "ǣ",
    "ea", "ēa", "eā", "eo", "ēo", "eō",
    "ie", "īe", "iē", "io", "īo", "iō",
}


# ── Consonants ────────────────────────────────────────────────────────────

# Explicitly marked palatals (editorial dot above).
_PALATAL_MARKED: dict[str, tuple[str, ...]] = {
    "ċ": ("tʃ",),
    "ġ": ("j",),
    "sċ": ("ʃ",),
    # Geminate palatal affricate. Emitted as two segments so the syllabifier
    # can split it (giving `dʒ.dʒ` across a syllable boundary); when the two
    # end up adjacent in one syllable, the final formatter collapses them to
    # `dʒː`.
    "ċġ": ("dʒ", "dʒ"),
}

# ⟨h⟩ + sonorant clusters (/xC/ phonemically; word-initial /x/ → [h]).
_H_CLUSTER: dict[str, tuple[str, str]] = {
    "hw": ("x", "w"),
    "hl": ("x", "l"),
    "hn": ("x", "n"),
    "hr": ("x", "r"),
}

_SIMPLE_CONS: dict[str, tuple[str, ...]] = {
    "m": ("m",), "n": ("n",),
    "p": ("p",), "b": ("b",), "t": ("t",), "d": ("d",),
    "l": ("l",), "r": ("r",), "w": ("w",),
    "f": ("f",), "s": ("s",),
    "þ": ("θ",), "ð": ("θ",),
    "h": ("x",),
    "j": ("j",), "z": ("z",),
    "x": ("k", "s"),
}

# Full tokenizer alphabet, longest first (so digraphs beat their leading char).
_ALL_TOKENS: list[str] = sorted(
    set(_DIPHTHONGS)
    | set(_MONOPHTHONGS)
    | set(_PALATAL_MARKED)
    | set(_H_CLUSTER)
    | set(_SIMPLE_CONS)
    | {"c", "g", "sc", "cg"},   # ambiguous / catch-alls
    key=len, reverse=True,
)

_VOWEL_TOKENS: set[str] = set(_DIPHTHONGS) | set(_MONOPHTHONGS)
_VOWEL_CHARS: set[str] = set("iɪeɛæaɑɒɔouʊyɯø")
_FRONT_VOWEL_CHARS: set[str] = set("iɪeɛæy")


# ── Tokenize ──────────────────────────────────────────────────────────────

def tokenize(word: str) -> list[str]:
    """Split an OE word into orthographic units by longest-match."""
    word = unicodedata.normalize("NFC", word).lower()
    tokens: list[str] = []
    i, n = 0, len(word)
    while i < n:
        if word[i] == "-":
            tokens.append("-")
            i += 1
            continue
        for tok in _ALL_TOKENS:
            if word.startswith(tok, i):
                tokens.append(tok)
                i += len(tok)
                break
        else:
            # Unknown character — pass through so the caller can see it.
            tokens.append(word[i])
            i += 1
    return tokens


# ── Orthography → phonemes ────────────────────────────────────────────────

def _next_tok(tokens: list[str], i: int) -> str | None:
    return tokens[i + 1] if i + 1 < len(tokens) else None


def _prev_tok(tokens: list[str], i: int) -> str | None:
    return tokens[i - 1] if i > 0 else None


def _resolve_c(tokens: list[str], i: int) -> tuple[str, ...]:
    """Unmarked ⟨c⟩: /k/ if the environment forces velar, else ambiguous 'K'.

    We don't try to guess palatal /tʃ/ from spelling — the user supplies
    editorial ⟨ċ⟩ for that, or later resolves 'K' via a lemma list."""
    nxt = _next_tok(tokens, i)
    if nxt in _FRONT_VOWEL_KEYS:
        return ("K",)
    if nxt is None or nxt == "-":
        return ("K",) if _prev_tok(tokens, i) in _FRONT_VOWEL_KEYS else ("k",)
    return ("k",)


def _resolve_g(tokens: list[str], i: int) -> tuple[str, ...]:
    """Unmarked ⟨g⟩: velar allophone [g]/[ɣ] where predictable, else 'G'."""
    nxt = _next_tok(tokens, i)
    if nxt in _FRONT_VOWEL_KEYS:
        return ("G",)
    prev = _prev_tok(tokens, i)
    if (nxt is None or nxt == "-") and prev in _FRONT_VOWEL_KEYS:
        return ("G",)
    # Velar allophony (single phoneme /ɣ~g/): [g] initial, after /n/, or as
    # geminate; [ɣ] elsewhere (typically post-vocalic).
    if prev is None or prev == "-" or prev == "n" or prev == "g":
        return ("g",)
    return ("ɣ",)


def to_phonemes(tokens: list[str]) -> list[str]:
    """Map tokens to a flat list of phoneme segments."""
    out: list[str] = []
    for i, tok in enumerate(tokens):
        if tok == "-":
            out.append("-")
        elif tok in _DIPHTHONGS:
            out.append(_DIPHTHONGS[tok])
        elif tok in _MONOPHTHONGS:
            out.append(_MONOPHTHONGS[tok])
        elif tok in _PALATAL_MARKED:
            out.extend(_PALATAL_MARKED[tok])
        elif tok in _H_CLUSTER:
            out.extend(_H_CLUSTER[tok])
        elif tok == "c":
            out.extend(_resolve_c(tokens, i))
        elif tok == "g":
            out.extend(_resolve_g(tokens, i))
        elif tok == "sc":
            out.append("ʃ")             # default; velar /sk/ is rare/lexical
        elif tok == "cg":
            out.extend(("dʒ", "dʒ"))    # default geminate palatal affricate
        elif tok in _SIMPLE_CONS:
            out.extend(_SIMPLE_CONS[tok])
        else:
            out.append(tok)
    return out


# ── Allophony ─────────────────────────────────────────────────────────────

def _is_vowel_seg(s: str) -> bool:
    return bool(s) and s[0] in _VOWEL_CHARS


def _last_vowel_char(s: str) -> str | None:
    for c in reversed(s):
        if c in _VOWEL_CHARS:
            return c
    return None


_VOICED_CONS: set[str] = set("mnŋlrjwbdgɣvðz") | {"dʒ"}


def _is_voiced(s: str) -> bool:
    return _is_vowel_seg(s) or s in _VOICED_CONS


def apply_allophony(segs: list[str]) -> list[str]:
    """Contextual allophony:
       - /n/ → [ŋ] before a velar plosive
       - /x/ → [h] at a word/morpheme onset, or between two vowels (assumed
               morpheme boundary since intervocalic /x/ was lost in OE);
               [ç] after a front vowel in coda position
       - /f θ s/ → [v ð z] between voiced sounds (approximates the
                    post-stressed-syllable voicing rule)
    """
    out = list(segs)
    n = len(out)

    for i in range(n - 1):
        if out[i] == "n" and out[i + 1] in {"k", "g", "K", "G"}:
            out[i] = "ŋ"

    for i, s in enumerate(out):
        if s != "x":
            continue
        prev = out[i - 1] if i > 0 else None
        nxt = out[i + 1] if i + 1 < n else None
        if prev is None or prev == "-":
            out[i] = "h"
        elif _is_vowel_seg(prev) and nxt is not None and _is_vowel_seg(nxt):
            out[i] = "h"
        elif _is_vowel_seg(prev) and nxt != "x":
            q = _last_vowel_char(prev)
            if q in _FRONT_VOWEL_CHARS:
                out[i] = "ç"

    for i, s in enumerate(out):
        if s not in {"f", "θ", "s"}:
            continue
        prev = out[i - 1] if i > 0 else None
        nxt = out[i + 1] if i + 1 < n else None
        if prev is None or nxt is None or prev == "-" or nxt == "-":
            continue
        if _is_voiced(prev) and _is_voiced(nxt):
            out[i] = {"f": "v", "θ": "ð", "s": "z"}[s]

    return out


# ── Syllabification ───────────────────────────────────────────────────────

# Legal Old English onset clusters (beyond any single consonant, which is
# always a legal onset). Derived from the phonotactics table.
_ONSET_CLUSTERS: set[str] = {
    "pr", "pl", "br", "bl", "tr", "tw", "dr", "dw",
    "kr", "kl", "kn", "kw",
    "gr", "gl", "gn", "ɣr", "ɣl", "ɣn",
    "fr", "fl", "fn", "θr", "θw",
    "wr", "wl",
    "ʃr",
    "hn", "hr", "hl", "hw",
    "xn", "xr", "xl", "xw",
    "sp", "st", "sk", "sm", "sn", "sl", "sw",
    "spr", "spl", "str", "skr",
}


def _is_legal_onset(onset: list[str]) -> bool:
    if len(onset) <= 1:
        return True
    return "".join(onset) in _ONSET_CLUSTERS


def _split_point(cluster: list[str]) -> int:
    """Offset within an intervocalic consonant cluster where the syllable
    boundary falls, chosen by maximum-onset subject to phonotactic legality.
    Geminates fall out naturally (double-C is never a legal onset)."""
    m = len(cluster)
    for split in range(m):
        if _is_legal_onset(cluster[split:]):
            return split
    return m


def syllabify(segs: list[str]) -> list[list[str]]:
    """Group segments into syllables. Morpheme boundaries ('-') stay in the
    output as single-element groups so `transcribe` can preserve them."""
    if "-" in segs:
        out: list[list[str]] = []
        buf: list[str] = []
        for s in segs:
            if s == "-":
                if buf:
                    out.extend(syllabify(buf))
                    buf = []
                out.append(["-"])
            else:
                buf.append(s)
        if buf:
            out.extend(syllabify(buf))
        return out

    vowel_ix = [i for i, s in enumerate(segs) if _is_vowel_seg(s)]
    if not vowel_ix:
        return [segs] if segs else []

    syllables: list[list[str]] = []
    start = 0
    for k, vi in enumerate(vowel_ix):
        if k + 1 == len(vowel_ix):
            syllables.append(segs[start:])
            break
        next_vi = vowel_ix[k + 1]
        cluster = segs[vi + 1:next_vi]
        split = _split_point(cluster)
        end = vi + 1 + split
        syllables.append(segs[start:end])
        start = end
    return syllables


# ── Morpheme lookup ───────────────────────────────────────────────────────

# Whole-morpheme phoneme overrides live in `morphemes.json` next to this
# module. The transcription pipeline splits the input on hyphens (editor-
# supplied morpheme markers) and consults this table before falling back to
# the generic token → phoneme mapping. This is how unmarked but historically
# palatal ⟨g⟩/⟨c⟩ get their correct realization, sidestepping the K/G
# ambiguity flag from `_resolve_c` / `_resolve_g`. Use `find_ambiguous.py` to
# see which morphemes still need entries.
_MORPHEME_TABLE_PATH = Path(__file__).with_name("morphemes.json")


def _load_morpheme_table() -> dict[str, tuple[str, ...]]:
    if not _MORPHEME_TABLE_PATH.exists():
        return {}
    with open(_MORPHEME_TABLE_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        unicodedata.normalize("NFC", k).lower(): tuple(v)
        for k, v in raw.items()
    }


_MORPHEME_PHONEMES: dict[str, tuple[str, ...]] = _load_morpheme_table()


def _phonemes_for_morpheme(morph: str) -> list[str]:
    """Phonemes for a single morpheme — table hit first, generic pipeline second."""
    key = unicodedata.normalize("NFC", morph).lower()
    if key in _MORPHEME_PHONEMES:
        return list(_MORPHEME_PHONEMES[key])
    return to_phonemes(tokenize(morph))


# ── Public API ────────────────────────────────────────────────────────────

def transcribe(word: str) -> str:
    """OE spelling → phoneme string with '.' as the syllable break."""
    word = unicodedata.normalize("NFC", word)
    morphs = word.split("-")
    phonemes: list[str] = []
    for i, m in enumerate(morphs):
        if i > 0:
            phonemes.append("-")
        if m:
            phonemes.extend(_phonemes_for_morpheme(m))
    # phones = apply_allophony(phonemes) ## Representations should be phonemic, not allophonic
    phones = phonemes
    syls = syllabify(phones)
    parts: list[str] = []
    for s in syls:
        text = "".join(s)
        # Collapse an intra-syllable geminate palatal affricate to length-mark
        # notation (cross-syllable geminates stay as `dʒ.dʒ` — the `.` between
        # them is inserted by the joiner below).
        text = text.replace("dʒdʒ", "dʒː")
        if text == "-":
            parts.append("-")
        else:
            if parts and parts[-1] != "-":
                parts.append(".")
            parts.append(text)
    return "".join(parts)


if __name__ == "__main__":
    words = sys.argv[1:] or [
        "bannan", "banan", "cniht", "hlūd", "singan", "eorðe",
        "weġ", "weċġ", "gōd", "cyning", "hūsian", "stān",
        "dæġ", "sceal", "nēah", "ġe-hālgian", "cild", "ċild",
        "gift", "bettra", "pyffan", "frēosan", "smiþ", "smiþas",
        # Morpheme-lookup cases.
        "ǣg", "ge-endian", "ge-hātan",
    ]
    width = max(len(w) for w in words)
    for w in words:
        print(f"{w:<{width}s}  →  {transcribe(w)}")
