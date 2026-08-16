##TODO:
## - Styling
## - Extraction Quality
##   - Create extraction metric
##   - Split defintion from Examples
##   - Handle Partial Verb Conjugations
##   - Multiple definitions rendered correctly
## - Entry Quality
##   - Render variants correctly
import re
import regex

import xml.etree.cElementTree as ET


tree = ET.parse("template.xml")
ET.register_namespace("", "http://www.w3.org/1999/xhtml")
ET.register_namespace("d", "http://www.apple.com/DTDs/DictionaryService-1.0.rng")
root = tree.getroot()


def create_entry(citation, d):
    entry = ET.Element("d:entry")
    entry.attrib["id"] = citation
    entry.attrib["d:title"] = citation

    for v in d["variants"]:
        var = ET.SubElement(entry, "d:index")
        var.attrib["d:value"] = v

    div1 = ET.SubElement(entry, "div")
    div1.attrib["d:priority"] = "2"
    name = ET.SubElement(div1, "h4")
    name.text = citation

    type_list = ET.SubElement(div1, "ol")
    type_list.attrib["type"] = "A"

    for k, v in d["class"].items():
        type_item = ET.SubElement(type_list, "li")
        class_div = ET.SubElement(type_item, "div")
        class_title = ET.SubElement(class_div, "h4")
        class_title.text = k
        class_list = ET.SubElement(class_div, "ol")
        for sense in v:
            item = ET.SubElement(class_list, "li")
            if len(sense["inflection"]) > 0:
                ending_info = "; ".join(
                    [
                        f"{k} {v}" if v != "" else f"{k}"
                        for k, v in sense["inflection"].items()
                    ]
                )
                item.text = f"({ending_info}) {sense['definition']}"
            else:
                item.text = sense["definition"]

    return entry


entry_d = {}

class_info = {
    "f.": "feminine noun",
    "m.": "masculine noun",
    "m?": "masculine noun",
    "n.": "neuter noun",
    "adj.": "adjective",
    "adi.": "adjective",
    "adv.": "adverb",
    "p.": "preterite singular",
    "pl.": "preterite plural",
    "pp.": "past participle",
    "pron.": "pronoun",
}

## PRE-PROCESSING ##
with open("./oe_dump.txt", "r") as f:
    text = f.read()
text = text.replace("æ-acute;", "ǽ")
text = text.replace("&a-long;", "á")
text = text.replace("&e-long;", "é")
text = text.replace("&i-long;", "í")
text = text.replace("&o-long;", "ó")
text = text.replace("&u-long;", "ú")
text = text.replace("&y-long;", "ý")
text = text.replace("&a-short;", "a")
text = text.replace("&e-short;", "e")
text = text.replace("&i-short;", "i")
text = text.replace("&o-short;", "o")
text = text.replace("&u-short;", "u")
text = text.replace("&y-short;", "y")
text = text.replace("&d-bar;", "ð")
text = text.replace("&aelig-acute;", "ǽ")
text = text.replace("&AElig-acute;", "Ǽ")

entries = re.split(r"\n+", text)
total = 0
success = 0
for e in entries:
    total += 1

    result = re.findall(r"([^;]+); ([^A-Z]+) ([A-Z].+)", e)

    if len(result) > 0:
        name, clas, def_examples = result[0]
        ## Process Definition(s) and Examples
        if def_examples.startswith("I. "):
            de_list = [
                d for d in re.split(r"[XVI]+\. ", def_examples) if d.strip() != ""
            ]
        else:
            de_list = [def_examples]

        d_list = []
        for i in de_list:
            try:
                ##First Pass
                result = re.findall("([^:]+) (:--|--) (.+)", i)
                if len(result) == 1:
                    df, _, examples = result[0]
                    examples = [
                        ex
                        for ex in regex.split(
                            "(?<=0|1|2|3|4|5|6|7|9)\. (?=\p{L})", examples
                        )
                        if len(ex.strip()) > 0
                    ]
                d_list.append((df, tuple(examples)))
            except:
                continue
        if len(d_list) < 1:
            continue

        ##Process Name Variants and Inflectional Info
        inflection = {}
        variants = []
        citation = None

        ##Handle Verbs
        is_verb = False
        if "trans." in clas:
            rendered_class = "transitive verb"
            is_verb = True
        if "intrans." in clas:
            rendered_class = "intransitive verb"
            is_verb = True
        for abbrev in [
            ("p\.", "pret. sg."),
            ("pl\.", "pret. pl."),
            ("pp\.", "past pp."),
            ("ic\.", "ic"),
            ("ðú\.", "ðú"),
            ("he\.", "he"),
        ]:
            if abbrev[0] == "pl\." and not is_verb:
                continue
            result = [
                a for a in re.findall(f"(?:^| ){abbrev[0]} ([^;]+);|,", clas) if a != ""
            ]
            if len(result) > 0:
                is_verb = True
                inflection[abbrev[1]] = result
        if is_verb:
            variants = name.lower().split(", ")
            citation = variants[0]
            print(citation)
            print(variants)
        else:
            try:
                rendered_class = class_info[clas]
                ##Handle Prepositions
                if clas.startswith("prep"):
                    rendered_class = "preposition"
                    if "acc." in clas:
                        inflection = {"takes accusative", ""}
                    elif "dat." in clas:
                        inflection = {"takes dative", ""}

                ##Handle Nominals
                if "noun" in rendered_class:
                    '''
                    for abbrev in [
                        ("g\.", "genitive"),
                        ("d\.", "dative"),
                        ("pl\. nom\. acc\.", "nominative/accusative plural"),
                    ]:
                    '''
                    try:
                        variants, ending = re.findall(r"^(.+), ([^,]+)$", name)[0]
                    except:
                        # print(name)
                        continue
                    variants = variants.lower().split(", ")
                    citation = variants[0]
                    if ending == "indecl":
                        inflection = {"indeclinable": ""}
                    else:
                        inflection = {"g.sg.": f"-{ending}"}

                ##Handle Adjectives / Adverbs
                if rendered_class in ["adjective", "adverb"]:
                    variants = name.lower().split(", ")
                    citation = variants[0]

                ##Render compound variants correctly
                if all([v.startswith("-") for v in variants[1:]]):
                    new_variants = []
                    for i, v in enumerate(variants):
                        if v in ["-ness", "-nys", "-nyss"]:
                            continue

                        if v.startswith("-"):
                            if "-" in citation:
                                stem = citation.split("-")[0]
                                new_variants.append(stem + v)
                            else:
                                print(f"no stem found for {citation} (for {v})")
                                continue
                                raise RuntimeError(
                                    f"no stem found for {citation} (for {v})"
                                )
                    variants = [citation] + new_variants
            except:
                continue


        success += 1
        if citation:
            for definition in d_list:
                if citation not in entry_d:
                    # entry_d[citation] = {'variants': variants, 'class':rendered_class, 'definition':definition, 'examples':examples, 'inflection':inflection}
                    entry_d[citation] = {
                        "variants": set(variants),
                        "class": {
                            rendered_class: [
                                {
                                    "definition": definition[0],
                                    "examples": definition[1],
                                    "inflection": inflection,
                                }
                            ]
                        },
                    }
                else:
                    if rendered_class not in entry_d[citation]["class"]:
                        entry_d[citation]["class"][rendered_class] = [
                            {
                                "definition": definition[0],
                                "examples": definition[1],
                                "inflection": inflection,
                            }
                        ]
                    else:
                        entry_d[citation]["class"][rendered_class].append(
                            {
                                "definition": definition[0],
                                "examples": definition[1],
                                "inflection": inflection,
                            }
                        )

    else:
        pass

for k, v in entry_d.items():
    ent = create_entry(k, v)
    root.append(ent)


with open("../MyDictionary.xml", "wb") as g:
    ET.indent(tree, space="\t", level=0)
    tree.write(g, encoding="utf-8")


print(f"PROCESSED {100*success/total}% LINES")
