"""Generate a safe Spanish duplicate deck workflow for the 4000 list."""

from __future__ import annotations

import argparse
import csv
import os
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


STATUS_REVIEWED = "reviewed"
STATUS_NEEDS_TRANSLATION = "needs_translation"


_SPANISH_ARTICLES = {"el", "la", "los", "las", "un", "una", "unos", "unas"}
_VOWELS = "aeiouáéíóúü"
_ACCENT_MAP = str.maketrans("áéíóúü", "aeiouu")
_ARTICLE_OVERRIDES = {
    "alcohol": "el",
    "análisis": "el",
    "arte": "el",
    "azúcar": "el",
    "agua": "el",
    "capital": "la",
    "catedral": "la",
    "clima": "el",
    "día": "el",
    "idioma": "el",
    "informe": "el",
    "llama": "la",
    "mano": "la",
    "mapa": "el",
    "mes": "el",
    "planeta": "el",
    "poema": "el",
    "problema": "el",
    "programa": "el",
    "sistema": "el",
    "tema": "el",
}
_NOUN_METADATA_OVERRIDES = {
    "agua": {
        "spanish_article": "el",
        "spanish_gender": "feminine",
        "spanish_number": "singular",
        "spanish_part_of_speech": "noun",
        "spanish_forms": "singular: el agua; plural: las aguas",
    },
    "catedral": {
        "spanish_article": "la",
        "spanish_gender": "feminine",
        "spanish_number": "singular",
        "spanish_part_of_speech": "noun",
        "spanish_forms": "singular: la catedral; plural: las catedrales",
    },
    "llama": {
        "spanish_article": "la",
        "spanish_gender": "feminine",
        "spanish_number": "singular",
        "spanish_part_of_speech": "noun",
        "spanish_forms": "singular: la llama; plural: las llamas",
    },
}
_NOUN_PHRASE_METADATA_OVERRIDES = {
    "el fútbol": {
        "spanish_article": "el",
        "spanish_gender": "masculine",
        "spanish_number": "singular",
        "spanish_part_of_speech": "noun",
        "spanish_forms": "singular: el fútbol; plural: los fútboles",
    },
    "el fútbol americano": {
        "spanish_article": "el",
        "spanish_gender": "masculine",
        "spanish_number": "singular",
        "spanish_part_of_speech": "noun",
        "spanish_forms": "singular: el fútbol americano; plural: los fútboles americanos",
    },
}
_ENGLISH_ARTICLE_SKIP = {
    "april",
    "august",
    "black",
    "blue",
    "brown",
    "december",
    "eight",
    "february",
    "five",
    "friday",
    "gray",
    "green",
    "january",
    "july",
    "june",
    "march",
    "may",
    "monday",
    "nine",
    "november",
    "october",
    "one",
    "orange",
    "purple",
    "red",
    "saturday",
    "september",
    "seven",
    "six",
    "sunday",
    "ten",
    "thursday",
    "tuesday",
    "two",
    "wednesday",
    "white",
    "yellow",
}


def normalize_word(value: str) -> str:
    """Normalize a vocab word for stable glossary matching."""
    text = re.sub(r"<[^>]+>", "", value or "")
    return " ".join(text.strip().lower().split())


def normalize_context(value: str) -> str:
    """Normalize source context for duplicate word disambiguation."""
    text = re.sub(r"<[^>]+>", "", value or "")
    return " ".join(text.strip().lower().split())


def context_key(english: str, english_meaning: str = "", english_example: str = "") -> str:
    """Build a glossary key that keeps duplicate English words with different senses separate."""
    return "\x1f".join(
        [
            "context",
            normalize_word(english),
            normalize_context(english_meaning),
            normalize_context(english_example),
        ]
    )


def normalize_header(value: str) -> str:
    """Normalize a header-like value for tolerant matching."""
    text = (value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _canonicalize_column_name(name: str) -> str:
    """Return canonical source-column names recognized by the parser."""
    key = normalize_header(name)
    aliases = {
        "guid": "guid",
        "notetype": "notetype",
        "note_type": "notetype",
        "deck": "deck",
        "card_number": "card_number",
        "card_number_1": "card_number",
        "image": "image",
        "word": "english_word",
        "english": "english_word",
        "english_word": "english_word",
        "front": "english_word",
        "phonetic": "phonetic",
        "sound": "sound",
        "ipa": "ipa",
        "meaning": "english_meaning",
        "english_meaning": "english_meaning",
        "example": "english_example",
        "english_example": "english_example",
    }
    return aliases.get(key, "")


def _slugify(value: str) -> str:
    """Build a stable lowercase slug for tags."""
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower())
    return slug.strip("_")


def _plain_spanish_word(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    text = text.strip().lower()
    text = text.strip("¿?¡!.,;:()[]{}\"'")
    return text


def _split_spanish_syllables(word: str) -> List[str]:
    """Return a readable approximate syllable split for pronunciation hints."""
    if not word:
        return []
    chunks = re.findall(r"[^aeiouáéíóúü]*[aeiouáéíóúü]+(?:[mnrsld](?=$|[^aeiouáéíóúü]))?|[^aeiouáéíóúü]+$", word)
    syllables = [chunk for chunk in chunks if chunk]
    if not syllables:
        return [word]
    return syllables


def _stress_index(word: str, syllables: Sequence[str]) -> int:
    for index, syllable in enumerate(syllables):
        if any(char in syllable for char in "áéíóú"):
            return index
    plain = word.translate(_ACCENT_MAP)
    if plain.endswith(("n", "s", "a", "e", "i", "o", "u")):
        return max(0, len(syllables) - 2)
    return len(syllables) - 1


def _turkish_upper(value: str) -> str:
    return value.upper()


def _sound_out_syllable(syllable: str) -> str:
    text = syllable.lower()
    text = text.translate(_ACCENT_MAP)
    protected = {
        "§CH§": "ç",
        "§LL§": "y",
        "§RR§": "rr",
        "§NY§": "ny",
        "§GWE§": "gwe",
        "§GWEE§": "gwi",
        "§GE§": "ge",
        "§GEE§": "gi",
        "§KE§": "ke",
        "§KEE§": "ki",
        "§SE§": "se",
        "§SEE§": "si",
        "§HE§": "he",
        "§HEE§": "hi",
        "§H§": "h",
    }
    result = text
    for source, token in [
        ("ch", "§CH§"),
        ("ll", "§LL§"),
        ("rr", "§RR§"),
        ("ñ", "§NY§"),
        ("güe", "§GWE§"),
        ("güi", "§GWEE§"),
        ("gue", "§GE§"),
        ("gui", "§GEE§"),
        ("que", "§KE§"),
        ("qui", "§KEE§"),
        ("ce", "§SE§"),
        ("ci", "§SEE§"),
        ("ge", "§HE§"),
        ("gi", "§HEE§"),
        ("j", "§H§"),
    ]:
        result = result.replace(source, token)
    for source, target in [
        ("z", "s"),
        ("v", "b"),
        ("h", ""),
        ("c", "k"),
        ("á", "a"),
        ("é", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ú", "u"),
        ("a", "a"),
        ("e", "e"),
        ("i", "i"),
        ("o", "o"),
        ("u", "u"),
    ]:
        result = result.replace(source, target)
    for token, target in protected.items():
        result = result.replace(token, target)
    return result


def _pronounce_word(word: str) -> str:
    plain = _plain_spanish_word(word)
    if not plain:
        return ""
    if plain in _SPANISH_ARTICLES:
        return plain
    syllables = _split_spanish_syllables(plain)
    stress = _stress_index(plain, syllables)
    sounded = []
    for index, syllable in enumerate(syllables):
        rendered = _sound_out_syllable(syllable)
        if index == stress:
            rendered = _turkish_upper(rendered)
        sounded.append(rendered)
    return "-".join(part for part in sounded if part)


def spanish_pronunciation_hint(value: str) -> str:
    """Build a Latin American Spanish pronunciation hint using Turkish-readable text."""
    words = [_pronounce_word(word) for word in re.split(r"\s+", re.sub(r"<[^>]+>", "", value or "").strip())]
    return " ".join(word for word in words if word)


def _spanish_tokens(value: str) -> List[str]:
    return re.findall(r"[a-záéíóúüñ]+", _plain_spanish_word(value))


def infer_spanish_metadata(spanish: str, english: str = "") -> Dict[str, str]:
    """Infer conservative grammar metadata from the reviewed Spanish headword."""
    tokens = _spanish_tokens(spanish)
    normalized_spanish = " ".join(tokens)
    article = tokens[0] if tokens and tokens[0] in _SPANISH_ARTICLES else ""
    head = tokens[1] if article and len(tokens) > 1 else (tokens[0] if tokens else "")
    metadata = {
        "spanish_article": article,
        "spanish_gender": "",
        "spanish_number": "",
        "spanish_part_of_speech": "",
        "spanish_forms": "",
    }
    if article:
        metadata["spanish_part_of_speech"] = "noun"
        metadata["spanish_gender"] = "feminine" if article in {"la", "las", "una", "unas"} else "masculine"
        metadata["spanish_number"] = "plural" if article in {"los", "las", "unos", "unas"} else "singular"
        singular_article = "la" if metadata["spanish_gender"] == "feminine" else "el"
        plural_article = "las" if metadata["spanish_gender"] == "feminine" else "los"
        if metadata["spanish_number"] == "plural":
            singular_head = _singularize_spanish_noun(head)
            plural_head = head
        else:
            singular_head = head
            plural_head = _pluralize_spanish_noun(head)
        metadata["spanish_forms"] = f"singular: {singular_article} {singular_head}; plural: {plural_article} {plural_head}"
        if head in _NOUN_METADATA_OVERRIDES:
            metadata.update(_NOUN_METADATA_OVERRIDES[head])
        if normalized_spanish in _NOUN_PHRASE_METADATA_OVERRIDES:
            metadata.update(_NOUN_PHRASE_METADATA_OVERRIDES[normalized_spanish])
    elif head.endswith(("ar", "er", "ir")):
        metadata["spanish_part_of_speech"] = "verb"
        metadata["spanish_forms"] = _regular_verb_forms(head)
    elif "/" in spanish:
        metadata["spanish_part_of_speech"] = "adjective"
        stem = head[:-1] if head.endswith(("o", "a")) else head
        if stem:
            metadata["spanish_forms"] = f"masc sg: {stem}o; fem sg: {stem}a; masc pl: {stem}os; fem pl: {stem}as"
    return metadata


def _starts_with_article(value: str) -> bool:
    tokens = _spanish_tokens(value)
    return bool(tokens and tokens[0] in _SPANISH_ARTICLES)


def _english_definition_marks_noun(english: str, english_meaning: str) -> bool:
    word = normalize_context(english)
    meaning = normalize_context(english_meaning)
    if not word or not meaning or word in _ENGLISH_ARTICLE_SKIP:
        return False
    if re.match(rf"^(a|an|the)\s+{re.escape(word)}\s+is\b", meaning):
        return True
    if meaning.startswith(f"{word} is "):
        return True
    return False


def _infer_definite_article(spanish: str) -> str:
    tokens = _spanish_tokens(spanish)
    if not tokens:
        return ""
    head = tokens[0]
    if head in _ARTICLE_OVERRIDES:
        return _ARTICLE_OVERRIDES[head]
    if head.endswith(("ción", "sión", "dad", "tad", "tud", "umbre")):
        return "la"
    if head.endswith(("aje", "or", "ma", "o")):
        return "el"
    if head.endswith("a"):
        return "la"
    if head.endswith(("e", "í", "ú")):
        return ""
    if head.endswith(("l", "n", "r", "s")):
        return "el"
    return ""


def add_article_to_clear_noun(spanish: str, english: str, english_meaning: str) -> str:
    """Add a definite article for clear noun-definition rows when gender is inferable."""
    if not spanish or _starts_with_article(spanish):
        return spanish
    metadata = infer_spanish_metadata(spanish, english)
    if metadata.get("spanish_part_of_speech") == "verb":
        return spanish
    if not _english_definition_marks_noun(english, english_meaning):
        return spanish
    article = _infer_definite_article(spanish)
    if not article:
        return spanish
    return f"{article} {spanish}"


def _pluralize_spanish_noun(noun: str) -> str:
    if not noun:
        return noun
    if noun.endswith(("s", "x")):
        return noun
    if noun[-1] in _VOWELS:
        return noun + "s"
    if noun.endswith("z"):
        return noun[:-1] + "ces"
    stem = noun.translate(str.maketrans({"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}))
    return stem + "es"


def _singularize_spanish_noun(noun: str) -> str:
    if noun.endswith("ces"):
        return noun[:-3] + "z"
    if noun.endswith("es") and len(noun) > 3:
        return noun[:-2]
    if noun.endswith("s") and len(noun) > 2:
        return noun[:-1]
    return noun


def _regular_verb_forms(verb: str) -> str:
    if len(verb) < 3:
        return ""
    ending = verb[-2:]
    endings = {
        "ar": "yo -o; tú -as; él/ella -a; nosotros -amos; ellos -an",
        "er": "yo -o; tú -es; él/ella -e; nosotros -emos; ellos -en",
        "ir": "yo -o; tú -es; él/ella -e; nosotros -imos; ellos -en",
    }.get(ending)
    if not endings:
        return ""
    return f"infinitive: {verb}; -{ending} pattern: {endings}; check irregular or stem-changing forms separately"


def _parse_header_directive(line: str, mapping: Dict[str, int]) -> None:
    """Parse header directives such as '#deck column:3' into column indexes."""
    text = line.strip()
    if not text.startswith("#"):
        return
    match = re.search(r"column:\s*(\d+)", text, flags=re.IGNORECASE)
    if not match:
        return
    index = int(match.group(1)) - 1
    name = text[1: match.start()].strip()
    canonical = _canonicalize_column_name(name)
    if canonical:
        mapping[canonical] = index


def _safe_field(row: Sequence[str], index: int) -> str:
    if index < 0 or index >= len(row):
        return ""
    return (row[index] or "").strip()


def _parse_known_4000_row(raw_row: Sequence[str]) -> Dict[str, str] | None:
    """Parse known 4000 EEW row layouts without trusting one shared word column."""
    notetype = _safe_field(raw_row, 1)
    if notetype == "4000 EEW":
        return {
            "guid": _safe_field(raw_row, 0),
            "notetype": notetype,
            "deck": _safe_field(raw_row, 2),
            "card_number": "",
            "image": _safe_field(raw_row, 4),
            "english_word": _safe_field(raw_row, 3),
            "phonetic": "",
            "sound": _safe_field(raw_row, 5),
            "ipa": _safe_field(raw_row, 10),
            "english_meaning": _safe_field(raw_row, 8),
            "english_example": _safe_field(raw_row, 9),
        }
    if notetype == "4000 EEW Extra":
        return {
            "guid": _safe_field(raw_row, 0),
            "notetype": notetype,
            "deck": _safe_field(raw_row, 2),
            "card_number": _safe_field(raw_row, 3),
            "image": _safe_field(raw_row, 4),
            "english_word": _safe_field(raw_row, 5),
            "phonetic": _safe_field(raw_row, 6),
            "sound": _safe_field(raw_row, 7),
            "ipa": _safe_field(raw_row, 8),
            "english_meaning": "",
            "english_example": "",
        }
    return None


def parse_source_deck(source_path: str) -> List[Dict[str, str]]:
    """Parse the source 4000 Essential English Words-style TSV deck."""
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(source_path)

    defaults = {
        "guid": 0,
        "notetype": 1,
        "deck": 2,
        "card_number": 3,
        "image": 4,
        "english_word": 5,
        "phonetic": 6,
        "sound": 7,
        "ipa": 8,
    }
    mapping: Dict[str, int] = {}
    rows: List[Dict[str, str]] = []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for raw_row in reader:
            if not raw_row:
                continue
            if len(raw_row) == 1 and raw_row[0].lstrip().startswith("#"):
                _parse_header_directive(raw_row[0], mapping)
                continue
            if not any(field.strip() for field in raw_row):
                continue

            row = _parse_known_4000_row(raw_row)
            if row is None:
                row = {
                    "guid": _safe_field(raw_row, mapping.get("guid", defaults["guid"])),
                    "notetype": _safe_field(raw_row, mapping.get("notetype", defaults["notetype"])),
                    "deck": _safe_field(raw_row, mapping.get("deck", defaults["deck"])),
                    "card_number": _safe_field(raw_row, mapping.get("card_number", defaults["card_number"])),
                    "image": _safe_field(raw_row, mapping.get("image", defaults["image"])),
                    "english_word": _safe_field(raw_row, mapping.get("english_word", defaults["english_word"])),
                    "phonetic": _safe_field(raw_row, mapping.get("phonetic", defaults["phonetic"])),
                    "sound": _safe_field(raw_row, mapping.get("sound", defaults["sound"])),
                    "ipa": _safe_field(raw_row, mapping.get("ipa", defaults["ipa"])),
                    "english_meaning": _safe_field(raw_row, mapping.get("english_meaning", -1)),
                    "english_example": _safe_field(raw_row, mapping.get("english_example", -1)),
                }
            if not row["english_word"]:
                continue
            rows.append(row)
    return rows


def _pick_header_key(headers: Dict[str, str], *candidates: str) -> str:
    for candidate in candidates:
        norm = normalize_header(candidate)
        if norm in headers:
            return headers[norm]
        for key in headers:
            if key == norm:
                return headers[key]
    return ""


def load_glossary(glossary_path: str | None) -> Dict[str, Dict[str, str]]:
    """Load reviewed Spanish glossary entries.

    Modern glossaries can include original English meaning/example columns, allowing
    duplicate words with different senses to use different Spanish translations.
    Older word-only glossaries are still accepted as a fallback.
    """
    if not glossary_path:
        return {}
    path = Path(glossary_path)
    if not path.exists():
        raise FileNotFoundError(glossary_path)

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters="\t,").delimiter
        except csv.Error:
            delimiter = "\t" if "\t" in sample else ","

        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            return {}

        headers = {normalize_header(name): name for name in reader.fieldnames}
        english_key = _pick_header_key(headers, "english", "english_word", "word")
        english_meaning_key = _pick_header_key(headers, "english_meaning", "meaning")
        english_example_key = _pick_header_key(headers, "english_example")
        spanish_key = _pick_header_key(headers, "spanish")
        spanish_meaning_key = _pick_header_key(headers, "spanish_meaning")
        example_key = _pick_header_key(headers, "spanish_example", "example")
        spanish_article_key = _pick_header_key(headers, "spanish_article", "article")
        spanish_gender_key = _pick_header_key(headers, "spanish_gender", "gender")
        spanish_number_key = _pick_header_key(headers, "spanish_number", "number")
        spanish_pos_key = _pick_header_key(headers, "spanish_part_of_speech", "part_of_speech", "pos", "word_class")
        spanish_forms_key = _pick_header_key(headers, "spanish_forms", "forms", "inflections")
        spanish_meaning_en_key = _pick_header_key(
            headers,
            "spanish_meaning_en",
            "spanish_meaning_english",
            "english_spanish_meaning",
            "spanish_meaning_translation",
        )
        spanish_example_en_key = _pick_header_key(
            headers,
            "spanish_example_en",
            "spanish_example_english",
            "english_spanish_example",
            "spanish_example_translation",
        )
        notes_key = _pick_header_key(headers, "notes")

        if not english_key or not spanish_key:
            return {}

        entries: List[Tuple[str, str, str, Dict[str, str]]] = []
        for row in reader:
            english = (row.get(english_key) or "").strip()
            if not english:
                continue
            entry = {
                "english": english,
                "english_meaning": (row.get(english_meaning_key) or "").strip() if english_meaning_key else "",
                "english_example": (row.get(english_example_key) or "").strip() if english_example_key else "",
                "spanish": (row.get(spanish_key) or "").strip(),
                "spanish_meaning": (row.get(spanish_meaning_key) or "").strip() if spanish_meaning_key else "",
                "spanish_example": (row.get(example_key) or "").strip() if example_key else "",
                "spanish_article": (row.get(spanish_article_key) or "").strip() if spanish_article_key else "",
                "spanish_gender": (row.get(spanish_gender_key) or "").strip() if spanish_gender_key else "",
                "spanish_number": (row.get(spanish_number_key) or "").strip() if spanish_number_key else "",
                "spanish_part_of_speech": (row.get(spanish_pos_key) or "").strip() if spanish_pos_key else "",
                "spanish_forms": (row.get(spanish_forms_key) or "").strip() if spanish_forms_key else "",
                "spanish_meaning_en": (row.get(spanish_meaning_en_key) or "").strip() if spanish_meaning_en_key else "",
                "spanish_example_en": (row.get(spanish_example_en_key) or "").strip() if spanish_example_en_key else "",
                "notes": (row.get(notes_key) or "").strip() if notes_key else "",
            }
            english_meaning = (row.get(english_meaning_key) or "").strip() if english_meaning_key else ""
            english_example = (row.get(english_example_key) or "").strip() if english_example_key else ""
            entries.append((english, english_meaning, english_example, entry))

        glossary: Dict[str, Dict[str, str]] = {}
        word_counts = Counter(normalize_word(english) for english, _, _, _ in entries)
        has_context_columns = bool(english_meaning_key or english_example_key)

        for english, english_meaning, english_example, entry in entries:
            word_key = normalize_word(english)
            if has_context_columns:
                glossary[context_key(english, english_meaning, english_example)] = entry
                if word_counts[word_key] == 1:
                    glossary[word_key] = entry
            else:
                glossary[word_key] = entry
    return glossary


def find_glossary_entry(
    glossary: Dict[str, Dict[str, str]],
    source_row: Dict[str, str],
) -> Dict[str, str] | None:
    """Find a reviewed glossary row, preferring exact source context over word-only fallback."""
    english = source_row.get("english_word", "")
    exact_key = context_key(
        english,
        source_row.get("english_meaning", ""),
        source_row.get("english_example", ""),
    )
    return glossary.get(exact_key) or glossary.get(normalize_word(english))


def build_spanish_rows(
    source_rows: Sequence[Dict[str, str]],
    glossary: Dict[str, Dict[str, str]],
    limit: int | None = None,
) -> List[Dict[str, str]]:
    """Build merged English->Spanish rows with reviewed/pending status."""
    selected_rows = list(source_rows)
    if limit is not None and limit >= 0:
        selected_rows = selected_rows[:limit]

    output_rows: List[Dict[str, str]] = []
    for source_row in selected_rows:
        english = source_row.get("english_word", "").strip()
        glossary_row = find_glossary_entry(glossary, source_row)
        is_reviewed = bool(glossary_row)

        english_meaning = (
            glossary_row.get("english_meaning", "").strip()
            if glossary_row and glossary_row.get("english_meaning")
            else re.sub(r"<[^>]+>", "", source_row.get("english_meaning", "")).strip()
        )
        english_example = (
            glossary_row.get("english_example", "").strip()
            if glossary_row and glossary_row.get("english_example")
            else re.sub(r"<[^>]+>", "", source_row.get("english_example", "")).strip()
        )
        spanish = glossary_row.get("spanish", "").strip() if glossary_row else ""
        if glossary_row:
            spanish = add_article_to_clear_noun(spanish, english, english_meaning)
        inferred = infer_spanish_metadata(spanish, english) if spanish else {}
        status = STATUS_REVIEWED if is_reviewed else STATUS_NEEDS_TRANSLATION
        source_deck = source_row.get("deck", "").strip()
        source_slug = _slugify(source_deck) or "source_unknown"
        tags = ["spanish", "from_4000_english", source_slug, status]

        output_rows.append(
            {
                "english": glossary_row.get("english", "").strip() if glossary_row and glossary_row.get("english") else re.sub(r"<[^>]+>", "", english).strip(),
                "spanish": spanish,
                "pronunciation_hint": spanish_pronunciation_hint(spanish) if spanish else "",
                "image": source_row.get("image", "").strip(),
                "english_meaning": english_meaning,
                "english_example": english_example,
                "spanish_meaning": glossary_row.get("spanish_meaning", "").strip() if glossary_row else "",
                "spanish_example": glossary_row.get("spanish_example", "").strip() if glossary_row else "",
                "spanish_meaning_en": (
                    glossary_row.get("spanish_meaning_en", "").strip()
                    or source_row.get("english_meaning", "").strip()
                    if glossary_row
                    else ""
                ),
                "spanish_example_en": (
                    glossary_row.get("spanish_example_en", "").strip()
                    or source_row.get("english_example", "").strip()
                    if glossary_row
                    else ""
                ),
                "spanish_article": (
                    glossary_row.get("spanish_article", "").strip()
                    or inferred.get("spanish_article", "")
                    if glossary_row
                    else ""
                ),
                "spanish_gender": (
                    glossary_row.get("spanish_gender", "").strip()
                    or inferred.get("spanish_gender", "")
                    if glossary_row
                    else ""
                ),
                "spanish_number": (
                    glossary_row.get("spanish_number", "").strip()
                    or inferred.get("spanish_number", "")
                    if glossary_row
                    else ""
                ),
                "spanish_part_of_speech": (
                    glossary_row.get("spanish_part_of_speech", "").strip()
                    or inferred.get("spanish_part_of_speech", "")
                    if glossary_row
                    else ""
                ),
                "spanish_forms": (
                    glossary_row.get("spanish_forms", "").strip()
                    or inferred.get("spanish_forms", "")
                    if glossary_row
                    else ""
                ),
                "notes": glossary_row.get("notes", "").strip() if glossary_row else "",
                "status": status,
                "source_deck": source_deck,
                "source_card": source_row.get("card_number", "").strip(),
                "tags": " ".join(tags),
            }
        )
    return output_rows


def _back_field_for_basic(record: Dict[str, str]) -> str:
    if record["status"] == STATUS_REVIEWED:
        parts = [f"English: {record['english']}"]
        if record.get("pronunciation_hint"):
            parts.append(f"Pronunciation: {record['pronunciation_hint']}")
        if record["spanish_meaning"]:
            parts.append(f"Spanish meaning: {record['spanish_meaning']}")
        if record["spanish_example"]:
            parts.append(f"Spanish example: {record['spanish_example']}")
        if record.get("spanish_example_en"):
            parts.append(f"Example in English: {record['spanish_example_en']}")
        if record.get("spanish_meaning_en"):
            parts.append(f"Meaning in English: {record['spanish_meaning_en']}")
        grammar_parts = []
        for label, key in [
            ("Part of speech", "spanish_part_of_speech"),
            ("Article", "spanish_article"),
            ("Gender", "spanish_gender"),
            ("Number", "spanish_number"),
            ("Forms", "spanish_forms"),
        ]:
            if record.get(key):
                grammar_parts.append(f"{label}: {record[key]}")
        if grammar_parts:
            parts.append("Grammar:\n" + "\n".join(grammar_parts))
        if record["notes"]:
            parts.append(f"Notes: {record['notes']}")
        return "\n".join(parts)
    return "TODO: Spanish translation needed"


def _write_tsv(path: Path, header: List[str], rows: List[Sequence[str]], include_import_headers: bool = False) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        if include_import_headers:
            handle.write("#separator:tab\n")
            handle.write("#html:true\n")
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_spanish_files(
    source_rows: Sequence[Dict[str, str]],
    glossary: Dict[str, Dict[str, str]],
    output_dir: str = "generated/spanish",
    limit: int | None = None,
) -> Tuple[str, str]:
    """
    Write review and basic TSV files and return file paths.

    Returns:
        (review_path, basic_path)
    """
    merged = build_spanish_rows(source_rows, glossary, limit=limit)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    review_rows = [
        [
            row["english"],
            row["english_meaning"],
            row["english_example"],
            row["spanish"],
            row["pronunciation_hint"],
            row["spanish_meaning"],
            row["spanish_example"],
            row["spanish_meaning_en"],
            row["spanish_example_en"],
            row["spanish_article"],
            row["spanish_gender"],
            row["spanish_number"],
            row["spanish_part_of_speech"],
            row["spanish_forms"],
            row["notes"],
            row["status"],
            row["source_deck"],
            row["source_card"],
            row["tags"],
        ]
        for row in merged
    ]
    basic_rows = [
        [
            "\n".join(
                value
                for value in (
                    row["image"],
                    row["spanish"] or row["english"],
                    row["pronunciation_hint"],
                )
                if value
            ),
            _back_field_for_basic(row),
            row["tags"],
        ]
        for row in merged
    ]

    review_path = output_path / "english_spanish_review.tsv"
    basic_path = output_path / "english_spanish_basic.tsv"

    _write_tsv(
        review_path,
        [
            "English",
            "English Meaning",
            "English Example",
            "Spanish",
            "Pronunciation Hint",
            "Spanish Meaning",
            "Spanish Example",
            "Spanish Meaning (English)",
            "Spanish Example (English)",
            "Spanish Article",
            "Spanish Gender",
            "Spanish Number",
            "Spanish Part of Speech",
            "Spanish Forms",
            "Notes",
            "Status",
            "Source Deck",
            "Source Card",
            "Tags",
        ],
        review_rows,
    )
    _write_tsv(
        basic_path,
        ["Front", "Back", "Tags"],
        basic_rows,
        include_import_headers=True,
    )

    return str(review_path), str(basic_path)


def summarize_rows(rows: Sequence[Dict[str, str]]) -> Dict[str, int]:
    counts = Counter(row["status"] for row in rows)
    total = len(rows)
    pending = counts[STATUS_NEEDS_TRANSLATION]
    return {
        "total_cards": total,
        "reviewed_count": total - pending,
        "pending_count": pending,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Spanish duplicate deck files from 4000 Essential English Words."
    )
    parser.add_argument("--source", default="4000 Essential English Words.txt", help="Source TSV deck path")
    parser.add_argument("--glossary", help="Optional reviewed glossary CSV/TSV path")
    parser.add_argument("--output-dir", default="generated/spanish", help="Output directory")
    parser.add_argument("--limit", type=int, help="Process at most N cards")
    parser.add_argument("--summary", action="store_true", help="Print counts only; no files written")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    source_rows = parse_source_deck(args.source)
    glossary = load_glossary(args.glossary)

    if args.summary:
        rows = build_spanish_rows(source_rows, glossary, limit=args.limit)
        summary = summarize_rows(rows)
        print(f"Total source cards: {summary['total_cards']}")
        print(f"Reviewed cards: {summary['reviewed_count']}")
        print(f"Pending cards: {summary['pending_count']}")
        return 0

    review_path, basic_path = write_spanish_files(
        source_rows,
        glossary,
        output_dir=args.output_dir,
        limit=args.limit,
    )

    print(f"Wrote review file: {os.path.abspath(review_path)}")
    print(f"Wrote basic import file: {os.path.abspath(basic_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
