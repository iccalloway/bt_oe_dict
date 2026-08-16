---
name: oe-grammar
description: Reference for Old English (Anglo-Saxon) orthography, noun declension paradigms, and verb conjugation paradigms as used in the Bosworth-Toller dictionary. Load when parsing, validating, or discussing OE dictionary entries — especially when interpreting abbreviations like `p.`, `pp.`, `pl.`, `gen.`, or when checking whether a form fits a paradigm.
---

# Old English grammar reference

Scope: enough OE morphology to disambiguate the Bosworth-Toller (BT) entry format used in this repo. Not a full grammar — reach for Campbell or Hogg for edge cases.

## Orthography

**Non-ASCII letters used in BT and OE editions:**
- `æ` / `Æ` — "ash", a front vowel between `a` and `e`.
- `þ` / `Þ` — "thorn", voiceless/voiced dental fricative (`th`).
- `ð` / `Ð` — "eth", same sounds as `þ`; the two are interchangeable in most manuscripts.
- `ƿ` / `Ƿ` — "wynn", equivalent to `w`. BT usually normalizes to `w`; original texts vary.
- `ȝ` / `Ȝ` — "yogh", rare in classical OE; more common in ME. BT prints `g`.

**Vowel-length marking (BT convention):**
- BT marks long vowels with an **acute** (`á é í ó ú ǽ ý`), not a macron (`ā ē ī ō ū ǣ ȳ`). Modern editions typically use macrons — treat the two as equivalent when comparing.
- `ǽ` = long ash. Long `œ` (rare) written `œ́`.
- Length is phonemic: `gód` "good" vs. `god` "god"; `ácnesnes` vs. `acnesnes`.

**Digraphs:** `cg` = /dʒ/ (`ecg` "edge"), `sc` = /ʃ/ usually (`scip` "ship"), `hw` = /ʍ/ (`hwæt`).

## Bosworth-Toller entry conventions

Standard layout of an entry:

```
headword, variant-form; gender-flag; other-forms  Gloss; Latin gloss :-- OE quotation English quotation. Citations. [Etymology.]
```

Key markers:

| Marker | Meaning |
|---|---|
| `;` between forms | separates flag groups (variant forms, gender, endings) |
| `,` between forms | continuation within a group |
| `:--` | separator between gloss and quotations |
| `[…]` | supplemental — typically etymology / cognates |
| `-X` (leading hyphen) | ending or form attached to the stem; the hyphen replaces the stem |
| `v.` | *vide*, "see"; cross-reference to another headword |
| `q. v.` | *quod vide*, "which see" |
| `Ð-` / `æ-` | small caps → uppercase in modern orthography |

Abbreviations seen in headers:

| Abbrev | Expansion | Notes |
|---|---|---|
| `m.` `f.` `n.` | masculine / feminine / neuter | noun gender flag |
| `sg.` `pl.` `du.` | singular / plural / dual | dual is rare, mostly pronouns |
| `nom.` `acc.` `gen.` `dat.` `inst.` | grammatical case | instrumental collapses into dative in late OE |
| `p.` | preterite (past tense) | verb entries |
| `pp.` | past participle | |
| `ppr.` | present participle | |
| `imp.` | imperative | |
| `indecl.` | indeclinable | |
| `w.` | "with" (governs a case: `w. dat.` = with the dative) |
| `ic ðú he wé gé hí` | 1sg 2sg 3sg 1pl 2pl 3pl pronouns | present-tense forms often listed with pronoun cue |

**Noun header pattern:** `headword, gen-sg-ending; gender` → e.g. `aac, e; f.` means fem. noun, gen. sg. `-e`. If multiple endings appear, each is labeled: `word, es, e; m; pl. as`.

**Verb header pattern:** `infinitive, present-forms; p. preterite-forms; pp. past-participle` → e.g. `a-bacan, ic -bace, ðú -bæcest, he -bæceþ, pl. -bacaþ; p. -bóc, pl. -bócon; pp. -bacen`.

## Noun declension paradigms

OE nouns fall into **strong** (vocalic-stem) and **weak** (n-stem) declensions. Use citation form + gender + gen. sg. ending to identify the class.

### Strong masculine a-stem (default class — most common)

Example: `stān` "stone".

|      | singular | plural |
|------|----------|--------|
| nom. | stān     | stānas |
| acc. | stān     | stānas |
| gen. | stānes   | stāna  |
| dat. | stāne    | stānum |

**Signature:** gen. sg. `-es`, nom. pl. `-as`.

### Strong neuter a-stem

Two subtypes distinguished by nom./acc. pl.:

- **Short stem** (`scip` "ship"): nom./acc. pl. `-u` → `scipu`.
- **Long stem** (`word` "word"): nom./acc. pl. bare → `word` (uninflected).

Other cases parallel masculine a-stem: gen. sg. `-es`, dat. sg. `-e`, gen. pl. `-a`, dat. pl. `-um`.

### Strong feminine ō-stem

Example: `giefu` "gift".

|      | singular | plural       |
|------|----------|--------------|
| nom. | giefu    | giefa/giefe  |
| acc. | giefe    | giefa/giefe  |
| gen. | giefe    | giefa        |
| dat. | giefe    | giefum       |

**Signature:** gen. sg. `-e`, nom. pl. `-a`/`-e`. Long-stem feminines (e.g. `lār` "learning") drop the nom. sg. `-u`.

### i-stem

Originally distinct, largely merged with a-stem (masc./neut.) or ō-stem (fem.) in classical OE. Trace: some short-stem masc. i-stems keep nom. pl. `-e` (`wine, wine`), long-stem drop it.

### u-stem

Small class; example `sunu` "son" (m.), `hand` "hand" (f.).

|      | sg (sunu) | pl     |
|------|-----------|--------|
| nom. | sunu      | suna   |
| gen. | suna      | suna   |
| dat. | suna      | sunum  |

### Weak (n-stem)

Example: `nama` "name" (m.), `tunge` "tongue" (f.), `ēage` "eye" (n.).

|      | m sg | f sg  | n sg  | pl (all genders) |
|------|------|-------|-------|-------------------|
| nom. | nama | tunge | ēage  | -an               |
| acc. | naman| tungan| ēage  | -an               |
| gen. | naman| tungan| ēagan | -ena              |
| dat. | naman| tungan| ēagan | -um               |

**Signature:** gen. sg. `-an`, gen. pl. `-ena`. Weak feminines end in `-e` in nom. sg.; weak masc. in `-a`; weak neut. in `-e` with acc. sg. also bare.

### Root-consonant (mutation) nouns

Handful of frequent nouns with i-mutation in dat. sg. and nom./acc. pl.: `fōt / fēt`, `tōþ / tēþ`, `man / men`, `mūs / mȳs`, `bōc / bēc`.

## Verb conjugation paradigms

OE verbs are **strong** (ablaut vowel change: `singan / sang / sungon / sungen`), **weak** (dental preterite: `-de` / `-ede` / `-ode`), **preterite-present** (present looks like a strong preterite; new weak preterite), or **anomalous** (`bēon`, `dōn`, `gān`, `willan`).

### Strong verb classes (identified by ablaut series)

| Class | Infinitive | 3sg pres | 1/3sg pret | pret pl | past part |
|-------|-----------|----------|------------|---------|-----------|
| I     | rīdan     | rīdeþ    | rād        | ridon   | riden     |
| II    | crēopan   | crīepþ   | crēap      | crupon  | cropen    |
| III   | bindan    | bint     | band       | bundon  | bunden    |
| III   | helpan    | hilpþ    | healp      | hulpon  | holpen    |
| IV    | beran     | birþ     | bær        | bǣron   | boren     |
| V     | metan     | mit(t)   | mæt        | mǣton   | meten     |
| VI    | faran     | fǣrþ     | fōr        | fōron   | faren     |
| VII   | hātan     | hǣt      | hēt        | hēton   | hāten     |
| VII   | feallan   | fielþ    | fēoll      | fēollon | feallen   |

`a-bacan` is class VI (`bacan / bōc / bōcon / bacen`). BT's `p. -bóc, pl. -bócon; pp. -bacen` matches this perfectly.

### Strong verb present indicative (uniform across classes)

Endings on the stem; 2/3 sg. usually trigger i-mutation of the root vowel.

| Person | ending | example (`bacan`, w/ i-mut) |
|--------|--------|-----------------------------|
| 1 sg   | -e     | ic bace                     |
| 2 sg   | -(e)st | ðū bæcest / bæcst           |
| 3 sg   | -(e)þ  | hē bæceþ / bæcþ             |
| pl     | -aþ    | wē / gē / hīe bacaþ         |

### Strong verb preterite indicative

| Person | ending | example (`bacan`) |
|--------|--------|-------------------|
| 1 sg   | ∅      | ic bōc            |
| 2 sg   | -e     | ðū bōce (uses pret-pl vowel grade) |
| 3 sg   | ∅      | hē bōc            |
| pl     | -on    | wē bōcon          |

### Weak verb classes

- **Class 1** (`-an` / `-de` or `-te`; often i-mutation): `dēman / dēmde / dēmed` "judge", `sēcan / sōhte / sōht` "seek".
- **Class 2** (`-ian` / `-ode` / `-od`; no i-mutation): `lufian / lufode / lufod` "love".
- **Class 3** (small closed class): `habban`, `libban`, `secgan`, `hycgan`.

Class 2 is enormous and productive — most new verbs go here.

### Preterite-present verbs (modals)

`witan` "know", `cunnan` "can", `sculan` "shall", `magan` "may", `mōtan` "must", `þurfan` "need", `dugan` "avail", `unnan` "grant", `āgan` "own". Present indic. 1/3 sg. is bare (no ending); preterite is weak.

Example `cunnan`: `ic can / ðū canst / hē can / wē cunnon; p. cūðe; pp. cūð`.

### Anomalous verbs

- **`bēon` / `wesan`** "be" — dual paradigm: `bēon`-forms carry habitual/future sense; `wesan`-forms are actual/past. Pres: `eom, eart, is, sindon` ~ `bēo, bist, biþ, bēoþ`; pret: `wæs, wǣre, wæs, wǣron`; pp. `(ge)wesen`.
- **`dōn`** "do" — `dō, dēst, dēþ, dōþ; p. dyde; pp. gedōn`.
- **`gān`** "go" — `gā, gǣst, gǣþ, gāþ; p. ēode; pp. gegān`.
- **`willan`** "will/want" — `wille, wilt, wile/wille, willaþ; p. wolde; pp. —`.

## Sanity-check heuristics when parsing an entry

- Verb entry gives you the infinitive + a few forms. Identify class by looking at the ablaut in `p.` / `pl.` / `pp.` — if the header shows `-ó- / -ó- / -a-` around class-VI stems like `bacan`, it's class VI.
- Noun entry: gen. sg. ending + gender picks the class. `-es; m.` → strong masc. a-stem. `-e; f.` → strong fem. ō-stem. `-an; m/f/n` → weak.
- If a form violates the expected paradigm, that's a signal to re-check the parse rather than trust it — many BT entries have OCR-era typos in the source text file, but the encoded paradigm should still cohere.
- BT abbreviates aggressively — always resolve `p.` → preterite (not "past"; use the `Tense` enum value `"preterite"`), `pp.` → past participle, `pl.` → plural.
