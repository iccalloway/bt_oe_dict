"""Pydantic models for the reverse-dictionary pipeline.

Two LLM-facing schemas:
- `LookupLemmas` — Phase 1 output: dictionary-form English lemmas extracted
  from a BT gloss so WordNet can look them up.
- `Disambiguation` — Phase 3 output: the WordNet synset that best matches
  an OE lemma's use of one English lemma, given co-text and Latin anchors.

Intermediate row types (`GlossToken`, `CandidateSet`, `DisambiguatedRow`,
`OEEquivalent`, `ReverseSense`, `ReverseEntry`) are internal to the pipeline
and never sent to the LLM; they exist so each stage can validate the
JSONL it reads and writes.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# LLM-facing schemas
# ---------------------------------------------------------------------------


class LookupLemmas(_Strict):
    """Phase 1 output. The LLM turns a messy 19th-c. gloss into dictionary-form
    English lemmas that WordNet can look up."""

    lemmas: list[str] = Field(
        description=(
            "Dictionary-form English lemmas extracted from the gloss. "
            "Lowercase. Singular for nouns, bare infinitive (no 'to') for verbs. "
            "Drop articles/prepositions ('a', 'the', 'of', 'to'), drop parentheticals, "
            "drop archaic spellings if a modern equivalent is obvious. "
            "One lemma per distinct sense-hint in the gloss: 'hope, expectation of "
            "something desired' → ['hope', 'expectation']; 'To take, receive, get, "
            "obtain' → ['take', 'receive', 'get', 'obtain']. Empty list if the gloss "
            "has no lookupable English lemmas (e.g. it's a cross-reference note)."
        )
    )


class Disambiguation(_Strict):
    """Phase 3 output. The LLM picks one WordNet synset from the candidate list."""

    selected_synset_id: str = Field(
        description=(
            "The WordNet synset ID (e.g. 'hope.n.01') that best matches how the "
            "OE lemma is used in this gloss. Must be one of the offered candidates "
            "verbatim, OR the exact string 'historical_unmapped' if none fit."
        )
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="0.0-1.0 confidence in the selection.",
    )
    rationale: str = Field(
        description="One or two sentences explaining the choice, citing Latin anchors or co-text where relevant.",
    )


# ---------------------------------------------------------------------------
# Internal pipeline row types
# ---------------------------------------------------------------------------


class QuotationRef(_Strict):
    """Pass-through record of a bilingual OE+English quotation from the source.
    Kept only when both `old_english` and `english` are present — the reverse
    dictionary wants readable examples, not orphan OE lines."""

    old_english: str
    english: str
    citations: Optional[str] = None


class GlossToken(_Strict):
    """One row of gloss_tokens.jsonl — one extracted English lemma tied back
    to the OE definition it came from."""

    oe_lemma: str
    pos: str  # "noun" | "verb"
    gender: Optional[str] = None  # "m"/"f"/"n" for nouns; else None
    variants: list[str] = Field(default_factory=list)
    english_token: str
    sibling_glosses: list[str] = Field(default_factory=list)
    latin_anchors: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    quotations: list[QuotationRef] = Field(default_factory=list)
    sense_path: str  # e.g. "I" or "I.(1)(a)"


class CandidateSynset(_Strict):
    synset_id: str
    definition: str
    examples: list[str] = Field(default_factory=list)
    lemmas: list[str] = Field(default_factory=list)


class CandidateSet(_Strict):
    """gloss_tokens row + WordNet candidates. Rows with 0 candidates get
    `status='unmapped'`; 1 candidate → `status='monosemous'`; ≥2 → `status='polysemous'`."""

    token: GlossToken
    wn_pos: str  # "n" | "v"
    candidates: list[CandidateSynset] = Field(default_factory=list)
    status: str  # "unmapped" | "monosemous" | "polysemous"


class DisambiguatedRow(_Strict):
    """CandidateSet with a resolved synset (or unmapped)."""

    token: GlossToken
    wn_pos: str
    selected_synset_id: str  # or "historical_unmapped"
    definition: Optional[str] = None  # WordNet definition of the selected synset
    confidence: float
    rationale: str


class OEEquivalent(_Strict):
    oe_lemma: str
    pos: str
    gender: Optional[str] = None
    variants: list[str] = Field(default_factory=list)
    latin_glosses: list[str] = Field(default_factory=list)
    attestations: list[str] = Field(default_factory=list)
    quotations: list[QuotationRef] = Field(default_factory=list)


class ReverseSense(_Strict):
    synset_id: str
    definition: Optional[str] = None
    oe_equivalents: list[OEEquivalent] = Field(default_factory=list)


class ReverseEntry(_Strict):
    english_lemma: str
    pos: str
    senses: list[ReverseSense] = Field(default_factory=list)
