from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


Gender = Literal["m", "f", "n"]
Case = Literal["nominative", "accusative", "genitive", "dative", "instrumental"]
Number = Literal["singular", "plural", "dual"]
Person = Literal["1", "2", "3"]
Tense = Literal[
    "present",
    "preterite",
    "past participle",
    "present participle",
    "imperative",
    "infinitive",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VerbForm(_Strict):
    form: str = Field(
        description="The conjugated verb form as written in the source, e.g. '-bace', '-bæcest', '-bóc'."
    )
    person: Optional[Person] = Field(
        default=None,
        description="Grammatical person (1/2/3) if inferable from a pronoun cue ('ic'=1, 'ðú'=2, 'he'=3); null otherwise.",
    )
    number: Optional[Number] = Field(
        default="singular",
        description="Grammatical number. 'pl.' in source → 'plural'; otherwise 'singular'.",
    )
    tense: Optional[Tense] = Field(
        default=None,
        description="Tense/form. Source abbreviations map as: (no marker) or pronoun cue → 'present'; 'p.' → 'preterite'; 'pp.' → 'past participle'; 'ppr.' → 'present participle'; 'imp.' → 'imperative'. Use 'preterite' not 'past'.",
    )


class CaseEnding(_Strict):
    ending: str = Field(
        description="Case ending as written in the source, without the leading hyphen (e.g. 'es', 'a', 'um')."
    )
    case: Case = Field(
        default="genitive",
        description="Grammatical case. When only a single ending is listed with no case marker, default to genitive.",
    )
    number: Number = Field(
        default="singular",
        description="Grammatical number. Default to singular unless the source specifies otherwise ('pl.', 'dat. pl.', etc.).",
    )


class AdjectivePOS(_Strict):
    category: Literal["adjective"] = "adjective"


class ConjunctionPOS(_Strict):
    category: Literal["conjunction"] = "conjunction"


class AdverbPOS(_Strict):
    category: Literal["adverb"] = "adverb"


class ParticiplePOS(_Strict):
    category: Literal["participle"] = "participle"


class PronounPOS(_Strict):
    category: Literal["pronoun"] = "pronoun"


class InterjectionPOS(_Strict):
    category: Literal["interjection"] = "interjection"


class PrepositionPOS(_Strict):
    category: Literal["preposition"] = "preposition"
    governs: List[Case] = Field(
        default_factory=list,
        description="Grammatical case(s) the preposition governs for this sense (e.g. 'with gen.' → ['genitive'], 'with dat.' → ['dative']). OE prepositions often govern multiple cases with different meanings — when the source splits by case at the Roman-numeral level ('I. with gen.', 'II. with dat.'), each Roman numeral becomes a separate Definition with its own PrepositionPOS.governs, and the nested (1)(a)... under it become sub_senses. Empty list if the source does not specify.",
    )


class VerbPOS(_Strict):
    category: Literal["verb"] = "verb"
    forms: List[VerbForm] = Field(
        default_factory=list,
        description="Conjugated forms listed after the citation form (e.g. 'ic -bace, ðú -bæcest, pl. -bacaþ; p. -bóc; pp. -bacen').",
    )


class NounPOS(_Strict):
    category: Literal["noun"] = "noun"
    gender: Optional[Gender] = Field(
        default=None,
        description="Grammatical gender: 'm' (masculine), 'f' (feminine), or 'n' (neuter). Taken from the semicolon-separated gender flag in the source.",
    )
    endings: List[CaseEnding] = Field(
        default_factory=list,
        description="Case endings listed after the citation form. A bare single ending is genitive singular; multi-form listings specify case/number explicitly.",
    )


POS = Annotated[
    Union[NounPOS, VerbPOS, AdjectivePOS, ConjunctionPOS, AdverbPOS, ParticiplePOS, PrepositionPOS, PronounPOS, InterjectionPOS],
    Field(discriminator="category"),
]


class Quotation(_Strict):
    old_english: Optional[str] = Field(
        default=None,
        description="Old English version of the quotation, verbatim from the source. Null if absent.",
    )
    latin: Optional[str] = Field(
        default=None,
        description="Latin version of the quotation, verbatim from the source. Null if absent.",
    )
    english: Optional[str] = Field(
        default=None,
        description="English translation as provided by the source. Do NOT translate — null if the source does not supply one.",
    )
    citations: Optional[str] = Field(
        default=None,
        description="Semicolon-separated citation references trailing the quotation (e.g. 'Homl. Th. ii. p. 268, 9').",
    )


class SubSense(_Strict):
    label: Optional[str] = Field(
        default=None,
        description="The verbatim source label for this sub-sense, e.g. '(1)', '(a)', '(α)', '(2)(b)'. Copy exactly as printed, including parentheses. Null if the source does not label this sub-sense.",
    )
    heading: Optional[str] = Field(
        default=None,
        description="Short editorial heading if the source provides one before the gloss (e.g. 'marking an object towards which motion is directed'). Null if there's no such heading.",
    )
    meaning: Optional[str] = Field(
        default=None,
        description="English gloss for this sub-sense. Same split rule as Definition.meaning. Null if the source provides no gloss (e.g. supplement `add :--` patterns where only quotations are added).",
    )
    latin: Optional[str] = Field(
        default=None,
        description="Latin gloss for this sub-sense when the source provides one. Same rules as Definition.latin.",
    )
    quotations: List[Quotation] = Field(
        default_factory=list,
        description="Quotation examples belonging to this sub-sense (appearing after ':--' within its bracket).",
    )
    sub_senses: List["SubSense"] = Field(
        default_factory=list,
        description="Further-nested sub-senses one level deeper. Use sparingly — only when the source clearly has a third tier under this sub-sense. Prefer flattening the label (e.g. '(1)(a)') into this SubSense's own `label` when the deeper structure is trivial.",
    )


SubSense.model_rebuild()


class Definition(_Strict):
    pos: POS = Field(description="Part-of-speech object; discriminated by 'category'.")
    sense_label: Optional[str] = Field(
        default=None,
        description="Roman-numeral tag the source uses for this definition, verbatim (e.g. 'I.', 'II.', 'III.'). Null when the entry has only one unlabeled sense.",
    )
    supplemental: Optional[str] = Field(
        default=None,
        description="Text enclosed in square brackets in the source (etymology, cognates, etc.). Null if absent.",
    )
    meaning: Optional[str] = Field(
        default=None,
        description="The English gloss appearing before ':--'. Copy verbatim. Null if the source provides no gloss — this happens in supplement entries where a Roman numeral is followed only by `add :--` (or `Add :--`), meaning 'add the following quotations to sense N of the main-dictionary entry, no new gloss'. In that case leave meaning null; do NOT write literal 'add' as the gloss. If a Latin translation is bundled in (typically after ';' or ',' — e.g. 'A law; lex' or 'To bake; pinsere, coquere'), extract it into `latin` instead and leave only the English portion here. Beware: not every semicolon separates Latin — cross-references like 'asked; p. of abiddan' are entirely English and stay here in full.",
    )
    latin: Optional[str] = Field(
        default=None,
        description="Latin translation of the meaning when the source provides one alongside the English gloss (e.g. 'lex' for 'A law; lex', or 'pinsere, coquere' for 'To bake; pinsere, coquere'). Null if the source gives no Latin gloss.",
    )
    quotations: List[Quotation] = Field(
        default_factory=list,
        description="Quotation examples appearing after ':--' at THIS level (not inside a nested (1)/(a) bracket — those belong to sub_senses).",
    )
    sub_senses: List[SubSense] = Field(
        default_factory=list,
        description="Nested sub-senses within this definition, one per (1)/(a)/(α) bracket in the source. When the source has a hierarchy like 'I. with gen. (1) direction of motion (a) marking an object', the Roman numeral maps to Definition, and each nested parenthesized bracket maps to one SubSense. Deeper mixed labels can be flattened into a single label like '(1)(a)'. Empty list when the definition has no sub-structure.",
    )


class EntryBatch(_Strict):
    entries: List["OldEnglishEntry"] = Field(
        description="One or more parsed entries from the source block. Almost always length 1. Length >1 only for collapsed multi-headword stub lines like 'á-bet, beþecian, -bicgan. v. á, B. IV, -bedecian, -bycgan.' — split each headword-with-its-target into its own OldEnglishEntry (here: three entries, each with citation_form + cross_references but no definitions)."
    )


class OldEnglishEntry(_Strict):
    citation_form: str = Field(
        description="The headword — the first listed form in the entry, before any comma."
    )
    variant_forms: List[str] = Field(
        default_factory=list,
        description="Variant spellings listed directly after the citation form, substantially similar to it (not conjugated/declined forms — those belong under pos.forms/pos.endings).",
    )
    definitions: List[Definition] = Field(
        default_factory=list,
        description="Distinct senses. Roman-numeral divisions (I., II., ...) in the source correspond to separate definition objects. Store the Roman tag in Definition.sense_label. Nested (1)/(a)/(α) brackets belong under Definition.sub_senses, not as new Definitions. For pure cross-reference stub entries where the source provides no gloss or POS (e.g. 'slecean. v. slæccan.'), leave this empty and put the target in cross_references.",
    )
    cross_references: List[str] = Field(
        default_factory=list,
        description="Cross-reference headwords the entry points to. Extract from 'v. XXX', 'V. XXX', 'Cf. XXX' notes (typically trailing the entry, occasionally mid-entry). Strip the 'v.'/'V.'/'Cf.' prefix and any parenthetical qualifiers, keeping just the bare headword. Comma-separated targets in source ('v. lang-tog, sceaft-tog') → separate list items. Empty list if none.",
    )


EntryBatch.model_rebuild()
