import argparse
import bz2
import csv
import html
import io
import re
import tarfile
from collections import Counter
from pathlib import Path

import spanish_grammar_levels


OUTPUT_DIR = Path("generated/spanish_core")
TATOEBA_DIR = Path("generated/sources/tatoeba")
TATOEBA_SELECTED_PATH = TATOEBA_DIR / "selected_spa_eng_pairs.tsv"
TATOEBA_LIMIT_PER_TARGET = 11
MIN_SELECTED_TATOEBA_PAIRS = 780

TATOEBA_LICENSE = "Tatoeba sentence text, CC BY 2.0 FR unless marked otherwise by contributor export."
TATOEBA_ATTRIBUTION = "Source: Tatoeba.org sentence IDs {spa_id}/{eng_id}."
INACCESSIBLE_AUDIO_SENTENCE_IDS = {
    "9912",
    "9921",
    "10454",
    "10576",
    "11720",
    "12864",
    "13955",
    "13966",
    "330078",
    "338575",
    "338577",
    "338625",
    "338658",
    "330673",
    "342298",
    "345183",
}
REJECT_TATOEBA_SENTENCE_IDS = {"2538", "2738", "2809", "2861", "3041", "330689"}
TATOEBA_SPANISH_TEXT_FIXES = {
    "410616": "A mí también me gustan los pasteles.",
}

EXTRA_PRODUCTION_EXAMPLES_BY_LEVEL = {
    "a1_1_foundations": 3,
    "a1_2_core_sentences": 2,
    "a2_1_daily_past": 3,
    "a2_2_natural_spanish": 2,
}

PATTERN_CARD_LEVELS = set()

AUDIO_CARD_QUOTAS_BY_LEVEL = {
    "a0_survival": 20,
    "a1_1_foundations": 70,
    "a1_2_core_sentences": 40,
    "a2_1_daily_past": 55,
    "a2_2_natural_spanish": 45,
    "b1_bridge": 10,
}


LEVEL_REMAP = {
    "basic subjunctive triggers": "b1_bridge",
    "conditional basics": "b1_bridge",
    "aunque indicative vs subjunctive recognition": "b1_bridge",
    "reported speech basics": "b1_bridge",
}

LEVELS = [
    {
        "id": "a0_survival",
        "deck": "Spanish Core Learning::A0 Survival",
        "goal": "Recognize sentence shape and produce very short controlled answers.",
    },
    {
        "id": "a1_1_foundations",
        "deck": "Spanish Core Learning::A1.1 Foundations",
        "goal": "Build present-tense identity, location, routine, and question patterns.",
    },
    {
        "id": "a1_2_core_sentences",
        "deck": "Spanish Core Learning::A1.2 Core Sentences",
        "goal": "Use high-frequency verbs, pronouns, likes, possession, and object patterns.",
    },
    {
        "id": "a2_1_daily_past",
        "deck": "Spanish Core Learning::A2.1 Daily Past",
        "goal": "Choose past frames, make comparisons, commands, and time expressions.",
    },
    {
        "id": "a2_2_natural_spanish",
        "deck": "Spanish Core Learning::A2.2 Natural Spanish",
        "goal": "Connect ideas and use more natural A2 structures.",
    },
    {
        "id": "b1_bridge",
        "deck": "Spanish Core Learning::B1 Bridge",
        "goal": "Preview high-value B1 patterns without pretending they are core A2.",
    },
]

LEVEL_DECKS = {level["id"]: level["deck"] for level in LEVELS}

FIELDS = [
    "SourceID",
    "DeckPath",
    "Level",
    "Topic",
    "CardType",
    "PromptMode",
    "Front",
    "Answer",
    "TypeAnswer",
    "Back",
    "Formula",
    "Examples",
    "Audio",
    "AudioURL",
    "AudioContributor",
    "AudioLicense",
    "AudioID",
    "Source",
    "Attribution",
    "Tags",
]


def _slug(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9áéíóúñü]+", "_", text)
    return text.strip("_")


def _clean_html(text):
    return str(text).replace("<br>", "\n").replace("<b>", "").replace("</b>", "")


def _examples_html(examples):
    return "<br>".join(f"- {example}" for example in examples)


def _strip_choice_prefix(text):
    return re.sub(r"^[A-Z]\)\s*", "", text).strip()


def _front_instruction(text):
    return f'<span class="front-instruction">{html.escape(text)}</span>'


def _front_label(text):
    return f'<span class="front-label">{html.escape(text)}</span>'


def _typed_contrast_front(choose_front):
    prompt = re.sub(r"(?i)^choose:?\s*", "", choose_front).strip()
    prompt = re.sub(r"<br>[A-Z]\)\s*[^<]+", "", prompt).strip()
    prompt = prompt.replace("___", "_____")
    return f"{_front_instruction('Type the correct Spanish form')}<br>{prompt}"


def _tags(level, topic, card_type):
    return " ".join(
        [
            "spanish_core",
            level,
            _slug(topic),
            card_type,
        ]
    )


def _level_for_topic(topic):
    return LEVEL_REMAP.get(topic["topic"], topic["level"])


def _strip_trailing_period(text):
    return re.sub(r"\.+$", "", text.rstrip())


def _card(
    source_id,
    level,
    topic,
    card_type,
    prompt_mode,
    front,
    answer,
    back,
    formula,
    examples,
    audio="",
    audio_url="",
    audio_contributor="",
    audio_license="",
    audio_id="",
    source="",
    attribution="",
):
    answer = _strip_trailing_period(answer)
    type_answer = answer if prompt_mode in {"type_exact", "type_compare"} else ""
    return {
        "SourceID": source_id,
        "DeckPath": LEVEL_DECKS[level],
        "Level": level,
        "Topic": topic,
        "CardType": card_type,
        "PromptMode": prompt_mode,
        "Front": front,
        "Answer": answer,
        "TypeAnswer": type_answer,
        "Back": back,
        "Formula": formula,
        "Examples": examples,
        "Audio": audio,
        "AudioURL": audio_url,
        "AudioContributor": audio_contributor,
        "AudioLicense": audio_license,
        "AudioID": audio_id,
        "Source": source,
        "Attribution": attribution,
        "Tags": _tags(level, topic, card_type),
    }


def _topic_cards(topic):
    level = _level_for_topic(topic)
    topic_name = topic["topic"]
    slug = _slug(topic_name)
    examples = _examples_html(topic["examples"])
    cards = [
        _card(
            f"{level}::{slug}::rule",
            level,
            topic_name,
            "rule",
            "self_grade",
            f"{_front_instruction('Rule')}<br>{html.escape(topic_name)}",
            topic["formula"],
            f"<b>Use</b><br>{topic['use']}<br><br><b>Common trap</b><br>{topic['trap']}",
            topic["formula"],
            examples,
        )
    ]
    choose_front, choose_answer, choose_reason = topic["choose"]
    typed_contrast_answer = _strip_choice_prefix(choose_answer)
    typed_contrast_mode = "type_exact" if len(typed_contrast_answer.split()) <= 4 else "type_compare"
    cards.append(
        _card(
            f"{level}::{slug}::typed_contrast",
            level,
            topic_name,
            "typed_contrast",
            typed_contrast_mode,
            _typed_contrast_front(choose_front),
            typed_contrast_answer,
            choose_reason,
            topic["formula"],
            examples,
        )
    )
    wrong, right, correction_reason = topic["correction"]
    cards.append(
        _card(
            f"{level}::{slug}::typed_correction",
            level,
            topic_name,
            "typed_correction",
            "type_compare",
            f"{_front_instruction('Correct the learner error')}<br><span class=\"wrong-spanish\">{wrong}</span>",
            right,
            correction_reason,
            topic["formula"],
            examples,
        )
    )
    prompt, answer, note = topic["production"]
    if prompt.startswith("Write in Spanish:"):
        prompt = prompt.replace("Write in Spanish:", f"{_front_instruction('Write in Spanish')}<br>", 1)
    prompt_mode = "type_exact" if len(answer.split()) <= 4 else "type_compare"
    cards.append(
        _card(
            f"{level}::{slug}::typed_production",
            level,
            topic_name,
            "typed_production",
            prompt_mode,
            prompt,
            answer,
            note,
            topic["formula"],
            examples,
        )
    )
    pattern_name, pattern_formula, pattern_examples = topic["pattern"]
    if level in PATTERN_CARD_LEVELS:
        cards.append(
            _card(
                f"{level}::{slug}::pattern",
                level,
                topic_name,
                "pattern",
                "type_compare",
                f"{_front_instruction('Use this mini pattern with a new word')}<br><span class=\"topic-label\">{topic_name}</span><br><b>{pattern_name}</b>",
                pattern_examples[0],
                "Produce one sentence using the pattern, then compare with the examples.",
                pattern_formula,
                _examples_html(pattern_examples),
            )
        )
    for index, example in enumerate(topic["examples"][: EXTRA_PRODUCTION_EXAMPLES_BY_LEVEL.get(level, 0)], start=1):
        cards.append(
            _card(
                f"{level}::{slug}::typed_production_extra_{index}",
                level,
                topic_name,
                "typed_production",
                "self_grade",
                (
                    f"{_front_instruction('Produce a Spanish sentence or chunk using this grammar pattern')}<br>"
                    f"<span class=\"topic-label\">{topic_name}</span><br>"
                    f"{topic['formula']}<br><br>"
                    f"{_front_instruction(f'Model target {index}: type your own answer, then compare')}"
                ),
                example,
                "Self-grade for the target pattern, not exact wording.",
                topic["formula"],
                examples,
            )
        )
    return cards


SENTENCE_TARGETS = [
    ("a0_survival", "sentence mining", "hay", r"\b[Hh]ay\b"),
    ("a0_survival", "sentence mining", "es", r"\b[Ee]s\b"),
    ("a0_survival", "sentence mining", "soy", r"\b[Ss]oy\b"),
    ("a0_survival", "sentence mining", "eres", r"\b[Ee]res\b"),
    ("a0_survival", "sentence mining", "son", r"\b[Ss]on\b"),
    ("a1_1_foundations", "sentence mining", "estoy", r"\b[Ee]stoy\b"),
    ("a1_1_foundations", "sentence mining", "estás", r"\b[Ee]stás\b"),
    ("a1_1_foundations", "sentence mining", "está", r"\b[Ee]stá\b"),
    ("a1_1_foundations", "sentence mining", "estamos", r"\b[Ee]stamos\b"),
    ("a1_1_foundations", "sentence mining", "están", r"\b[Ee]stán\b"),
    ("a1_1_foundations", "sentence mining", "tengo", r"\b[Tt]engo\b"),
    ("a1_1_foundations", "sentence mining", "tienes", r"\b[Tt]ienes\b"),
    ("a1_1_foundations", "sentence mining", "tiene", r"\b[Tt]iene\b"),
    ("a1_1_foundations", "sentence mining", "tenemos", r"\b[Tt]enemos\b"),
    ("a1_1_foundations", "sentence mining", "quiero", r"\b[Qq]uiero\b"),
    ("a1_1_foundations", "sentence mining", "quieres", r"\b[Qq]uieres\b"),
    ("a1_1_foundations", "sentence mining", "quiere", r"\b[Qq]uiere\b"),
    ("a1_1_foundations", "sentence mining", "puedo", r"\b[Pp]uedo\b"),
    ("a1_1_foundations", "sentence mining", "puedes", r"\b[Pp]uedes\b"),
    ("a1_1_foundations", "sentence mining", "puede", r"\b[Pp]uede\b"),
    ("a1_1_foundations", "sentence mining", "voy", r"\b[Vv]oy\b"),
    ("a1_1_foundations", "sentence mining", "vas", r"\b[Vv]as\b"),
    ("a1_1_foundations", "sentence mining", "va", r"\b[Vv]a\b"),
    ("a1_1_foundations", "sentence mining", "vamos", r"\b[Vv]amos\b"),
    ("a1_1_foundations", "sentence mining", "hoy", r"\b[Hh]oy\b"),
    ("a1_1_foundations", "sentence mining", "mañana", r"\b[Mm]añana\b"),
    ("a1_1_foundations", "sentence mining", "ahora", r"\b[Aa]hora\b"),
    ("a1_1_foundations", "sentence mining", "siempre", r"\b[Ss]iempre\b"),
    ("a1_1_foundations", "sentence mining", "nunca", r"\b[Nn]unca\b"),
    ("a1_2_core_sentences", "sentence mining", "me gusta", r"\b[Mm]e gusta\b"),
    ("a1_2_core_sentences", "sentence mining", "me gustan", r"\b[Mm]e gustan\b"),
    ("a1_2_core_sentences", "sentence mining", "te gusta", r"\b[Tt]e gusta\b"),
    ("a1_2_core_sentences", "sentence mining", "le gusta", r"\b[Ll]e gusta\b"),
    ("a1_2_core_sentences", "sentence mining", "voy a", r"\b[Vv]oy a\b"),
    ("a1_2_core_sentences", "sentence mining", "vas a", r"\b[Vv]as a\b"),
    ("a1_2_core_sentences", "sentence mining", "va a", r"\b[Vv]a a\b"),
    ("a1_2_core_sentences", "sentence mining", "tengo que", r"\b[Tt]engo que\b"),
    ("a1_2_core_sentences", "sentence mining", "tienes que", r"\b[Tt]ienes que\b"),
    ("a1_2_core_sentences", "sentence mining", "porque", r"\b[Pp]orque\b"),
    ("a1_2_core_sentences", "sentence mining", "pero", r"\b[Pp]ero\b"),
    ("a2_1_daily_past", "sentence mining", "ayer", r"\b[Aa]yer\b"),
    ("a2_1_daily_past", "sentence mining", "anoche", r"\b[Aa]noche\b"),
    ("a2_1_daily_past", "sentence mining", "fui", r"\b[Ff]ui\b"),
    ("a2_1_daily_past", "sentence mining", "fue", r"\b[Ff]ue\b"),
    ("a2_1_daily_past", "sentence mining", "tuve", r"\b[Tt]uve\b"),
    ("a2_1_daily_past", "sentence mining", "hice", r"\b[Hh]ice\b"),
    ("a2_1_daily_past", "sentence mining", "dije", r"\b[Dd]ije\b"),
    ("a2_1_daily_past", "sentence mining", "vi", r"\b[Vv]i\b"),
    ("a2_1_daily_past", "sentence mining", "era", r"\b[Ee]ra\b"),
    ("a2_1_daily_past", "sentence mining", "estaba", r"\b[Ee]staba\b"),
    ("a2_1_daily_past", "sentence mining", "tenía", r"\b[Tt]enía\b"),
    ("a2_1_daily_past", "sentence mining", "cuando", r"\b[Cc]uando\b"),
    ("a2_1_daily_past", "sentence mining", "hace", r"\b[Hh]ace\b"),
    ("a2_1_daily_past", "sentence mining", "más que", r"\b[Mm]ás que\b"),
    ("a2_1_daily_past", "sentence mining", "menos que", r"\b[Mm]enos que\b"),
    ("a2_2_natural_spanish", "sentence mining", "para", r"\b[Pp]ara\b"),
    ("a2_2_natural_spanish", "sentence mining", "por", r"\b[Pp]or\b"),
    ("a2_2_natural_spanish", "sentence mining", "desde hace", r"\b[Dd]esde hace\b"),
    ("a2_2_natural_spanish", "sentence mining", "acabo de", r"\b[Aa]cabo de\b"),
    ("a2_2_natural_spanish", "sentence mining", "he", r"\b[Hh]e\b"),
    ("a2_2_natural_spanish", "sentence mining", "has", r"\b[Hh]as\b"),
    ("a2_2_natural_spanish", "sentence mining", "ha", r"\b[Hh]a\b"),
    ("a2_2_natural_spanish", "sentence mining", "hemos", r"\b[Hh]emos\b"),
    ("a2_2_natural_spanish", "sentence mining", "lo que", r"\b[Ll]o que\b"),
    ("a2_2_natural_spanish", "sentence mining", "aunque", r"\b[Aa]unque\b"),
    ("a2_2_natural_spanish", "sentence mining", "entonces", r"\b[Ee]ntonces\b"),
    ("a2_2_natural_spanish", "sentence mining", "también", r"\b[Tt]ambién\b"),
    ("a2_2_natural_spanish", "sentence mining", "tampoco", r"\b[Tt]ampoco\b"),
    ("b1_bridge", "sentence mining", "quiero que", r"\b[Qq]uiero que\b"),
    ("b1_bridge", "sentence mining", "espero que", r"\b[Ee]spero que\b"),
    ("b1_bridge", "sentence mining", "si", r"\b[Ss]i\b"),
    ("b1_bridge", "sentence mining", "sería", r"\b[Ss]ería\b"),
    ("b1_bridge", "sentence mining", "podría", r"\b[Pp]odría\b"),
]
TARGET_PATTERNS = {target: pattern for _, _, target, pattern in SENTENCE_TARGETS}

def _word_count(sentence):
    return len(re.findall(r"\w+", sentence, flags=re.UNICODE))


def _is_clean_sentence(sentence):
    if any(marker in sentence for marker in ("@", "http://", "https://", "\t")):
        return False
    if "Muiriel" in sentence:
        return False
    if re.search(r"[{}<>\\[\\]]", sentence):
        return False
    if sentence.count("!") > 1 or sentence.count(";") > 0:
        return False
    return 3 <= _word_count(sentence) <= 12


def _level_sentence_length_ok(level, spa_text, eng_text):
    spa_words = _word_count(spa_text)
    eng_words = _word_count(eng_text)
    limits = {
        "a0_survival": 7,
        "a1_1_foundations": 9,
        "a1_2_core_sentences": 10,
        "a2_1_daily_past": 12,
        "a2_2_natural_spanish": 12,
        "b1_bridge": 14,
    }
    max_words = limits.get(level, 12)
    return spa_words <= max_words and eng_words <= max_words + 2


def _level_content_ok(level, spa_text, eng_text):
    text = f"{spa_text} {eng_text}".lower()
    if "..." in text:
        return False
    if "pegarle un tiro" in text:
        return False
    if level in {"a0_survival", "a1_1_foundations"}:
        early_level_noise = [
            "muiriel",
            "la mayoría",
            "loco",
            "loca",
            "gordo",
            "furious",
            "crazy",
            "fat",
            "aunque",
            "si acaso",
            "episodio",
            "cuando crezca",
            "matemática",
            "embarazada",
            "en su mayoría",
        ]
        if any(pattern in text for pattern in early_level_noise):
            return False
    if level == "a0_survival":
        a0_noise = [
            "porque",
            "cuando",
            "si ",
            "como ",
            "habría",
            "sabéis",
            "siento que",
            "déjame",
            "giants",
            "paul",
            "susan",
            "benjamín",
            "albergue",
            "visiones",
            "verdaderas",
            "desafortunadamente",
            "inocencia",
            "impaciente",
            "tonto",
            "ángel",
            "mi tipo",
            "bastante",
            "gatos son pardos",
            "pregunta cómo",
            "él dijo",
            "responsable del error",
        ]
        if any(pattern in text for pattern in a0_noise):
            return False
    return True


def _load_sentences(path):
    rows = {}
    with bz2.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) >= 3:
                sentence_id, lang, text = row[0], row[1], row[2]
                if _is_clean_sentence(text):
                    rows[sentence_id] = text
    return rows


def _load_audio_metadata():
    audio_path = TATOEBA_DIR / "sentences_with_audio.tar.bz2"
    if not audio_path.exists():
        return {}
    rows = {}
    with tarfile.open(audio_path, "r:bz2") as archive:
        handle = archive.extractfile("sentences_with_audio.csv")
        if handle is None:
            return {}
        reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8", newline=""), delimiter="\t")
        for row in reader:
            if len(row) >= 3:
                rows[row[0]] = {
                    "audio_id": row[1],
                    "contributor": "" if row[2] == r"\N" else row[2],
                    "license": "" if len(row) < 4 or row[3] == r"\N" else row[3],
                }
    return rows


def _tatoeba_pair_rows(limit_per_target):
    spa_path = TATOEBA_DIR / "spa_sentences.tsv.bz2"
    eng_path = TATOEBA_DIR / "eng_sentences.tsv.bz2"
    links_path = TATOEBA_DIR / "spa-eng_links.tsv.bz2"
    if not links_path.exists():
        links_path = TATOEBA_DIR / "links.tar.bz2"
    if not (spa_path.exists() and eng_path.exists() and links_path.exists()):
        return []

    spa = _load_sentences(spa_path)
    eng = _load_sentences(eng_path)
    audio = _load_audio_metadata()
    pairs_by_target = {(level, target): [] for level, _, target, _ in SENTENCE_TARGETS}
    target_by_regex = [(level, topic, target, re.compile(pattern)) for level, topic, target, pattern in SENTENCE_TARGETS]
    seen_target_pairs = set()
    seen_target_english = set()
    seen_target_spanish_text = set()

    def visit_pair(left_id, right_id):
        if left_id in spa and right_id in eng:
            spa_id, eng_id = left_id, right_id
        elif right_id in spa and left_id in eng:
            spa_id, eng_id = right_id, left_id
        else:
            return
        spa_text = spa[spa_id]
        eng_text = eng[eng_id]
        if not _is_clean_sentence(eng_text):
            return
        for level, topic, target, pattern in target_by_regex:
            bucket = pairs_by_target[(level, target)]
            if len(bucket) >= limit_per_target:
                continue
            pair_key = (level, target, spa_id, eng_id)
            if pair_key in seen_target_pairs:
                continue
            english_key = (level, target, eng_id)
            if english_key in seen_target_english:
                continue
            spanish_text_key = (level, target, spa_text.lower())
            if spanish_text_key in seen_target_spanish_text:
                continue
            if not _level_sentence_length_ok(level, spa_text, eng_text):
                continue
            if not _level_content_ok(level, spa_text, eng_text):
                continue
            if pattern.search(spa_text):
                audio_meta = audio.get(spa_id, {})
                seen_target_pairs.add(pair_key)
                seen_target_english.add(english_key)
                seen_target_spanish_text.add(spanish_text_key)
                bucket.append(
                    {
                        "level": level,
                        "topic": topic,
                        "target": target,
                        "spa_id": spa_id,
                        "spa_text": spa_text,
                        "eng_id": eng_id,
                        "eng_text": eng_text,
                        "audio_id": audio_meta.get("audio_id", ""),
                        "audio_contributor": audio_meta.get("contributor", ""),
                        "audio_license": audio_meta.get("license", ""),
                    }
                )

    if links_path.name.endswith(".tsv.bz2"):
        with bz2.open(links_path, "rt", encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle, delimiter="\t"):
                if len(row) >= 2:
                    visit_pair(row[0], row[1])
    else:
        with tarfile.open(links_path, "r:bz2") as archive:
            handle = archive.extractfile("links.csv")
            if handle is None:
                return []
            reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8", newline=""), delimiter="\t")
            for left_id, right_id in reader:
                visit_pair(left_id, right_id)

    pairs = []
    for level, _, target, _ in SENTENCE_TARGETS:
        pairs.extend(pairs_by_target[(level, target)])
    return pairs


def _write_selected_tatoeba_pairs(pairs):
    TATOEBA_SELECTED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TATOEBA_SELECTED_PATH.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "level",
            "topic",
            "target",
            "spa_id",
            "spa_text",
            "eng_id",
            "eng_text",
            "audio_id",
            "audio_contributor",
            "audio_license",
            "license",
        ]
        writer = csv.DictWriter(handle, delimiter="\t", lineterminator="\n", fieldnames=fieldnames)
        writer.writeheader()
        for row in pairs:
            writer.writerow(
                {
                    **row,
                    "license": TATOEBA_LICENSE,
                }
            )


def _apply_tatoeba_text_fixes(row):
    fixed = dict(row)
    if fixed.get("spa_id") in TATOEBA_SPANISH_TEXT_FIXES:
        fixed["spa_text"] = TATOEBA_SPANISH_TEXT_FIXES[fixed["spa_id"]]
    return fixed


def _load_tatoeba_pairs(limit_per_target=TATOEBA_LIMIT_PER_TARGET):
    if TATOEBA_SELECTED_PATH.exists():
        with TATOEBA_SELECTED_PATH.open(encoding="utf-8", newline="") as handle:
            rows = [
                _apply_tatoeba_text_fixes(row)
                for row in csv.DictReader(handle, delimiter="\t")
                if row["spa_id"] not in REJECT_TATOEBA_SENTENCE_IDS
            ]
        if len(rows) >= MIN_SELECTED_TATOEBA_PAIRS:
            return rows

    pairs = _tatoeba_pair_rows(limit_per_target)
    pairs = [_apply_tatoeba_text_fixes(row) for row in pairs]
    _write_selected_tatoeba_pairs(pairs)
    return [row for row in pairs if row["spa_id"] not in REJECT_TATOEBA_SENTENCE_IDS]


def _audio_url(spa_id):
    return f"https://audio.tatoeba.org/sentences/spa/{spa_id}.mp3"


def _audio_usable(row):
    return row.get("audio_id") and row["spa_id"] not in INACCESSIBLE_AUDIO_SENTENCE_IDS


def _assign_sentence_roles(rows, audio_card_quotas=None):
    audio_card_quotas = audio_card_quotas or AUDIO_CARD_QUOTAS_BY_LEVEL
    roles = {}
    audio_counts = Counter()
    dictation_counts = Counter()

    for row in rows:
        level = row["level"]
        spa_id = row["spa_id"]
        if (
            spa_id in roles
            or not _audio_usable(row)
            or audio_counts[level] >= audio_card_quotas.get(level, 0)
        ):
            continue
        roles[spa_id] = "audio_cloze"
        audio_counts[level] += 1

    for row in rows:
        level = row["level"]
        spa_id = row["spa_id"]
        if (
            spa_id in roles
            or not _audio_usable(row)
            or dictation_counts[level] >= DICTATION_LEVEL_QUOTAS.get(level, 0)
        ):
            continue
        roles[spa_id] = "dictation"
        dictation_counts[level] += 1

    return roles


DICTATION_QUOTA = 50
DICTATION_LEVEL_QUOTAS = {
    "a0_survival": 8,
    "a1_1_foundations": 14,
    "a1_2_core_sentences": 10,
    "a2_1_daily_past": 10,
    "a2_2_natural_spanish": 8,
}


def _dictation_cards():
    """Full-sentence dictation: hear audio, type the entire Spanish sentence."""
    pairs = _load_tatoeba_pairs()
    roles = _assign_sentence_roles(pairs)
    cards = []
    used_sentence_ids = set()
    for row in pairs:
        spa_id = row["spa_id"]
        if spa_id in used_sentence_ids or roles.get(spa_id) != "dictation":
            continue
        used_sentence_ids.add(spa_id)
        level = row["level"]
        spa_text = row["spa_text"]
        eng_text = row["eng_text"]
        sound = f"[sound:tatoeba_spa_{spa_id}.mp3]"
        source = f"Tatoeba spa:{spa_id} eng:{row['eng_id']}"
        attribution = TATOEBA_ATTRIBUTION.format(spa_id=spa_id, eng_id=row["eng_id"])
        cards.append(
            _card(
                f"tatoeba_dictation::{level}::{spa_id}::{row['eng_id']}",
                level,
                "short dictation",
                "dictation",
                "type_compare",
                f"{sound}<br><br>{_front_instruction('Type the full Spanish sentence you hear')}",
                spa_text,
                f"Compare spelling, accents, and punctuation, then replay once.<br><br>Meaning: {eng_text}",
                "Full dictation; tests word boundaries, accents, and spelling.",
                f"- {spa_text}<br>- {eng_text}",
                audio=sound,
                audio_url=_audio_url(spa_id),
                audio_contributor=row.get("audio_contributor", "") or "Tatoeba contributor not listed in export",
                audio_license=row.get("audio_license", "") or row.get("license", "") or TATOEBA_LICENSE,
                audio_id=row.get("audio_id", ""),
                source=source,
                attribution=attribution,
            )
        )
    return cards


VERB_PARADIGMS = [
    ("a0_survival", "ser", "present", "soy | eres | es | somos | sois | son", "Identity, origin, occupation, characteristics"),
    ("a0_survival", "estar", "present", "estoy | estás | está | estamos | estáis | están", "Location, temporary state, condition"),
    ("a0_survival", "tener", "present", "tengo | tienes | tiene | tenemos | tenéis | tienen", "Possession, age, obligation (tener que)"),
    ("a0_survival", "ir", "present", "voy | vas | va | vamos | vais | van", "Movement, future (ir a + infinitive)"),
    ("a0_survival", "hay", "present", "hay (invariable)", "Existence: there is / there are"),
    ("a1_1_foundations", "hablar", "present", "hablo | hablas | habla | hablamos | habláis | hablan", "Regular -ar: to speak"),
    ("a1_1_foundations", "comer", "present", "como | comes | come | comemos | coméis | comen", "Regular -er: to eat"),
    ("a1_1_foundations", "vivir", "present", "vivo | vives | vive | vivimos | vivís | viven", "Regular -ir: to live"),
    ("a1_1_foundations", "hacer", "present", "hago | haces | hace | hacemos | hacéis | hacen", "Irregular yo: to do/make"),
    ("a1_1_foundations", "poder", "present", "puedo | puedes | puede | podemos | podéis | pueden", "Stem change o→ue: can, to be able"),
    ("a1_1_foundations", "querer", "present", "quiero | quieres | quiere | queremos | queréis | quieren", "Stem change e→ie: to want"),
    ("a1_2_core_sentences", "decir", "present", "digo | dices | dice | decimos | decís | dicen", "Irregular yo: to say/tell"),
    ("a1_2_core_sentences", "ver", "present", "veo | ves | ve | vemos | veis | ven", "Regular-ish: to see/watch"),
    ("a1_2_core_sentences", "dar", "present", "doy | das | da | damos | dais | dan", "Irregular yo: to give"),
    ("a1_2_core_sentences", "saber", "present", "sé | sabes | sabe | sabemos | sabéis | saben", "Irregular yo: to know (facts/skills)"),
    ("a2_1_daily_past", "ser", "preterite", "fui | fuiste | fue | fuimos | fuisteis | fueron", "To be (past) — fully irregular, same as ir"),
    ("a2_1_daily_past", "ir", "preterite", "fui | fuiste | fue | fuimos | fuisteis | fueron", "To go (past) — same forms as ser"),
    ("a2_1_daily_past", "tener", "preterite", "tuve | tuviste | tuvo | tuvimos | tuvisteis | tuvieron", "To have (past) — uv stem"),
    ("a2_1_daily_past", "hacer", "preterite", "hice | hiciste | hizo | hicimos | hicisteis | hicieron", "To do/make (past) — z in él/ella"),
    ("a2_1_daily_past", "poder", "preterite", "pude | pudiste | pudo | pudimos | pudisteis | pudieron", "To be able (past) — regular preterite"),
    ("a2_1_daily_past", "querer", "preterite", "quise | quisiste | quiso | quisimos | quisisteis | quisieron", "To want (past) — regular preterite"),
    ("a2_1_daily_past", "decir", "preterite", "dije | dijiste | dijo | dijimos | dijisteis | dijeron", "To say (past) — j stem"),
    ("a2_1_daily_past", "ver", "preterite", "vi | viste | vio | vimos | visteis | vieron", "To see (past) — regular-ish"),
    ("a2_1_daily_past", "dar", "preterite", "di | diste | dio | dimos | disteis | dieron", "To give (past) — regular-ish"),
    ("a2_1_daily_past", "hablar", "preterite", "hablé | hablaste | habló | hablamos | hablasteis | hablaron", "Regular -ar preterite"),
    ("a2_1_daily_past", "comer", "preterite", "comí | comiste | comió | comimos | comisteis | comieron", "Regular -er preterite"),
    ("a2_1_daily_past", "vivir", "preterite", "viví | viviste | vivió | vivimos | vivisteis | vivieron", "Regular -ir preterite"),
    ("a2_2_natural_spanish", "ser", "imperfect", "era | eras | era | éramos | erais | eran", "To be (background) — fully irregular"),
    ("a2_2_natural_spanish", "ir", "imperfect", "iba | ibas | iba | íbamos | ibais | iban", "To go (background) — fully irregular"),
    ("a2_2_natural_spanish", "ver", "imperfect", "veía | veías | veía | veíamos | veíais | veían", "To see (background) — irregular -ía"),
    ("a2_2_natural_spanish", "hablar", "imperfect", "hablaba | hablabas | hablaba | hablábamos | hablabais | hablaban", "Regular -ar imperfect"),
    ("a2_2_natural_spanish", "comer", "imperfect", "comía | comías | comía | comíamos | comíais | comían", "Regular -er imperfect"),
    ("a2_2_natural_spanish", "vivir", "imperfect", "vivía | vivías | vivía | vivíamos | vivíais | vivían", "Regular -ir imperfect"),
    ("a2_2_natural_spanish", "tener", "imperfect", "tenía | tenías | tenía | teníamos | teníais | tenían", "To have (background) — irregular -ía"),
    ("a2_2_natural_spanish", "hacer", "imperfect", "hacía | hacías | hacía | hacíamos | hacíais | hacían", "To do/make (background) — irregular -ía"),
    ("a2_2_natural_spanish", "poder", "imperfect", "podía | podías | podía | podíamos | podíais | podían", "To be able (background) — irregular -ía"),
    ("a2_2_natural_spanish", "querer", "imperfect", "quería | querías | quería | queríamos | queríais | querían", "To want (background) — irregular -ía"),
    ("a2_2_natural_spanish", "decir", "imperfect", "decía | decías | decía | decíamos | decíais | decían", "To say (background) — irregular -ía"),
    ("a2_2_natural_spanish", "saber", "imperfect", "sabía | sabías | sabía | sabíamos | sabíais | sabían", "To know (background) — irregular -ía"),
    ("b1_bridge", "ser", "future", "seré | serás | será | seremos | seréis | serán", "To be (future) — regular future"),
    ("b1_bridge", "tener", "future", "tendré | tendrás | tendrá | tendremos | tendréis | tendrán", "To have (future) — d stem"),
    ("b1_bridge", "hacer", "future", "haré | harás | hará | haremos | haréis | harán", "To do/make (future) — c drops"),
    ("b1_bridge", "poder", "future", "podré | podrás | podrá | podremos | podréis | podrán", "To be able (future) — e drops"),
    ("b1_bridge", "querer", "future", "querré | querrás | querrá | querremos | querréis | querrán", "To want (future) — r doubles"),
    ("b1_bridge", "decir", "future", "diré | dirás | dirá | diremos | diréis | dirán", "To say (future) — irregular stem"),
    ("b1_bridge", "saber", "future", "sabré | sabrás | sabrá | sabremos | sabréis | sabrán", "To know (future) — e drops"),
    ("b1_bridge", "poner", "future", "pondré | pondrás | pondrá | pondremos | pondréis | pondrán", "To put (future) — d stem"),
    ("b1_bridge", "salir", "future", "saldré | saldrás | saldrá | saldremos | saldréis | saldrán", "To go out (future) — d stem"),
    ("b1_bridge", "venir", "future", "vendré | vendrás | vendrá | vendremos | vendréis | vendrán", "To come (future) — d stem"),
]


def _verb_paradigm_cards():
    """Systematic verb conjugation grid cards."""
    cards = []
    for level, verb, tense, paradigm, meaning in VERB_PARADIGMS:
        cards.append(
            _card(
                f"verb_paradigm::{level}::{verb}::{tense}",
                level,
                f"verb conjugation: {verb}",
                "verb_paradigm",
                "type_compare",
                f"{_front_instruction('Conjugate')} <b>{verb}</b> – {tense} tense<br><span class=\"type-note\">Type all 6 forms separated by |</span>",
                paradigm,
                f"{verb} ({tense}) = {meaning}<br>{paradigm}",
                f"Systematic paradigm drill for {verb}.",
                f"- {paradigm}",
            )
        )
    return cards


L1_L2_PRODUCTION = [
    ("a0_survival", "I am a student.", "Soy estudiante", "ser + profession (no article)"),
    ("a0_survival", "I am not tired.", "No estoy cansado", "estar + temporary state; no before verb"),
    ("a0_survival", "I have a book.", "Tengo un libro", "tener + un + noun"),
    ("a0_survival", "I am going home.", "Voy a casa", "ir + a + destination"),
    ("a0_survival", "There is a problem.", "Hay un problema", "hay = invariable existence"),
    ("a0_survival", "I speak Spanish.", "Hablo español", "regular -ar: hablo (yo)"),
    ("a0_survival", "I eat bread.", "Como pan", "regular -er: como (yo)"),
    ("a0_survival", "I live in Madrid.", "Vivo en Madrid", "regular -ir: vivo (yo) + en + city"),
    ("a0_survival", "Yes, I want it.", "Sí, lo quiero", "sí with accent = yes; lo = direct object"),
    ("a0_survival", "No, I do not know.", "No, no lo sé", "saber (yo) = sé; double no is natural"),
    ("a1_1_foundations", "We study at night.", "Estudiamos por la noche", "regular -ar: estudiamos (nosotros) + por + time"),
    ("a1_1_foundations", "She works today.", "Ella trabaja hoy", "regular -ar: trabaja (ella) + time at end"),
    ("a1_1_foundations", "I can help you.", "Puedo ayudarte", "poder (yo) = puedo; ayudar + te = enclitic"),
    ("a1_1_foundations", "He wants coffee.", "Él quiere café", "querer stem change e→ie: quiere (él)"),
    ("a1_1_foundations", "I do not understand.", "No entiendo", "entender stem change e→ie: entiendo (yo)"),
    ("a1_1_foundations", "What do you do?", "¿Qué haces", "hacer: haces (tú); question marks"),
    ("a1_1_foundations", "Where do you live?", "¿Dónde vives", "vivir: vives (tú); question marks"),
    ("a1_1_foundations", "I am eating.", "Estoy comiendo", "estar + gerund: present progressive"),
    ("a1_1_foundations", "They are sleeping.", "Están durmiendo", "estar + gerund; o→u stem change in gerund"),
    ("a1_1_foundations", "It is cold today.", "Hace frío hoy", "hacer + weather: hace frío/calor"),
    ("a1_2_core_sentences", "I have to study today.", "Tengo que estudiar hoy", "tener que + infinitive = have to"),
    ("a1_2_core_sentences", "I like Spanish.", "Me gusta el español", "gustar + singular = gusta; el + language"),
    ("a1_2_core_sentences", "I like books.", "Me gustan los libros", "gustar + plural = gustan; los + noun"),
    ("a1_2_core_sentences", "I see the book.", "Veo el libro", "ver: veo (yo); el + noun"),
    ("a1_2_core_sentences", "I see it.", "Lo veo", "lo = direct object pronoun (masculine singular)"),
    ("a1_2_core_sentences", "I give her a book.", "Le doy un libro", "dar: doy (yo); le = indirect object (her)"),
    ("a1_2_core_sentences", "I tell her the truth.", "Le digo la verdad", "decir: digo (yo); le = indirect object"),
    ("a1_2_core_sentences", "I know the answer.", "Sé la respuesta", "saber: sé (yo); la = direct object"),
    ("a1_2_core_sentences", "I know how to cook.", "Sé cocinar", "saber + infinitive = know how to"),
    ("a1_2_core_sentences", "What are you doing?", "¿Qué estás haciendo", "estar + gerund: present progressive question"),
    ("a2_1_daily_past", "I went to the cinema yesterday.", "Fui al cine ayer", "ser/ir preterite: fui; al = a + el"),
    ("a2_1_daily_past", "I had a good time.", "Lo pasé bien", "idiom: lo pasé bien = had a good time"),
    ("a2_1_daily_past", "She told me the news.", "Me dijo las noticias", "decir preterite: dijo; me = indirect object"),
    ("a2_1_daily_past", "We ate at a restaurant.", "Comimos en un restaurante", "comer preterite: comimos (nosotros)"),
    ("a2_1_daily_past", "I could not go.", "No pude ir", "poder preterite: pude; no before verb"),
    ("a2_1_daily_past", "They left early.", "Salieron temprano", "salir preterite: salieron (ellos)"),
    ("a2_1_daily_past", "I did it yesterday.", "Lo hice ayer", "hacer preterite: hice; lo = direct object"),
    ("a2_1_daily_past", "What did you say?", "¿Qué dijiste", "decir preterite: dijiste (tú)"),
    ("a2_1_daily_past", "He gave me a gift.", "Me dio un regalo", "dar preterite: dio; me = indirect object"),
    ("a2_2_natural_spanish", "I used to live in Lima.", "Vivía en Lima", "vivir imperfect: vivía (yo) = used to live"),
    ("a2_2_natural_spanish", "It was raining.", "Llovía", "llover imperfect: llovía = was raining"),
    ("a2_2_natural_spanish", "When I was a child, I played soccer.", "Cuando era niño, jugaba al fútbol", "era = imperfect ser; jugaba = imperfect jugar"),
    ("a2_2_natural_spanish", "She was reading when I arrived.", "Leía cuando llegué", "leía = imperfect; llegué = preterite; contrast"),
    ("a2_2_natural_spanish", "We always went to the beach.", "Íbamos siempre a la playa", "ir imperfect: íbamos (nosotros) = used to go"),
    ("a2_2_natural_spanish", "I was tired yesterday.", "Estaba cansado ayer", "estar imperfect: estaba = was (state)"),
    ("a2_2_natural_spanish", "He knew the answer.", "Sabía la respuesta", "saber imperfect: sabía = knew (knew how)"),
    ("a2_2_natural_spanish", "This book is more expensive.", "Este libro es más caro", "ser + más + adjective = comparative"),
    ("a2_2_natural_spanish", "I run as fast as you.", "Corro tan rápido como tú", "tan + adjective + como = as...as"),
    ("b1_bridge", "I want you to come.", "Quiero que vengas", "querer que + subjunctive: vengas"),
    ("b1_bridge", "I hope it rains.", "Espero que llueva", "esperar que + subjunctive: llueva"),
    ("b1_bridge", "If I had time, I would travel.", "Si tuviera tiempo, viajaría", "si + imperfect subjunctive + conditional"),
    ("b1_bridge", "When I arrive, I will call you.", "Cuando llegue, te llamaré", "cuando + subjunctive (future) + future"),
    ("b1_bridge", "He said he was tired.", "Dijo que estaba cansado", "reported speech: dijo que + imperfect"),
]


def _l1_l2_production_cards():
    """English prompt -> Spanish sentence-level production."""
    cards = []
    for level, english, spanish, note in L1_L2_PRODUCTION:
        cards.append(
            _card(
                f"l1_l2::{level}::{_slug(english)}",
                level,
                "English to Spanish production",
                "typed_production",
                "type_compare",
                f"{_front_instruction('Type the Spanish for')}<br>{english}",
                spanish,
                note,
                "",
                "",
            )
        )
    return cards


INTERLEAVED_CONTRASTS = [
    ("a1_1_foundations", "ser vs estar (identity vs state)",
     "María _____ maestra.", "María es maestra", "ser = permanent identity (profession)",
     "María _____ cansada.", "María está cansada", "estar = temporary state"),
    ("a1_1_foundations", "ser vs estar (origin vs location)",
     "Soy _____ España.", "Soy de España", "ser de = origin",
     "Estoy _____ España.", "Estoy en España", "estar en = location"),
    ("a1_1_foundations", "present vs present progressive",
     "Ella _____ español todos los días.", "Ella habla español todos los días", "habitual = simple present",
     "Ella _____ español ahora.", "Ella está hablando español ahora", "right now = present progressive"),
    ("a1_2_core_sentences", "saber vs conocer",
     "_____ la respuesta.", "Sé la respuesta", "saber = know facts/skills",
     "_____ a María.", "Conozco a María", "conocer + a = know people"),
    ("a1_2_core_sentences", "gustar singular vs plural",
     "Me _____ el café.", "Me gusta el café", "singular noun → gusta",
     "Me _____ los libros.", "Me gustan los libros", "plural noun → gustan"),
    ("a2_1_daily_past", "preterite vs imperfect (event vs background)",
     "Ayer _____ al cine.", "Ayer fui al cine", "preterite = completed event with specific time",
     "De niño, _____ al cine cada semana.", "De niño, iba al cine cada semana", "imperfect = habitual/repeated past"),
    ("a2_1_daily_past", "preterite vs imperfect (action vs state)",
     "_____ la puerta y entré.", "Abrí la puerta y entré", "preterite = completed action in sequence",
     "La puerta _____ abierta.", "La puerta estaba abierta", "imperfect = ongoing state/description"),
    ("a2_1_daily_past", "ser vs ir preterite (same forms)",
     "_____ a la fiesta anoche.", "Fui a la fiesta anoche", "ir preterite: fui = went (movement + destination)",
     "_____ muy feliz anoche.", "Fui muy feliz anoche", "ser preterite: fui = was (event/state)"),
    ("a2_2_natural_spanish", "por vs para (reason vs purpose)",
     "Estudio _____ mi futuro.", "Estudio para mi futuro", "para = purpose/destination",
     "Estudio _____ interés.", "Estudio por interés", "por = reason/cause"),
    ("a2_2_natural_spanish", "imperfect vs preterite (description vs event)",
     "Hacía sol y los niños _____ en el parque.", "Hacía sol y los niños jugaban en el parque", "imperfect = background description",
     "De repente, _____ a llover.", "De repente, empezó a llover", "preterite = sudden event"),
    ("a2_2_natural_spanish", "ser vs estar (characteristic vs result)",
     "El café _____ muy caliente.", "El café está muy caliente", "estar = current state/condition",
     "El café _____ una bebida oscura.", "El café es una bebida oscura", "ser = defining characteristic"),
    ("b1_bridge", "indicative vs subjunctive (fact vs doubt)",
     "Creo que _____ mañana.", "Creo que viene mañana", "creer que + indicative = belief",
     "No creo que _____ mañana.", "No creo que venga mañana", "no creer que + subjunctive = doubt"),
    ("b1_bridge", "conditional vs imperfect (hypothetical vs past)",
     "Si tuviera dinero, _____ un coche.", "Si tuviera dinero, compraría un coche", "conditional = hypothetical result",
     "Cuando era joven, _____ mucho.", "Cuando era joven, compraba mucho", "imperfect = past habitual"),
]


def _interleaved_contrast_cards():
    """Cards that mix two competing patterns to train real-time discrimination."""
    cards = []
    for level, topic_name, sent1_front, sent1_ans, sent1_note, sent2_front, sent2_ans, sent2_note in INTERLEAVED_CONTRASTS:
        cards.append(
            _card(
                f"interleaved::{level}::{_slug(topic_name)}::1",
                level,
                topic_name,
                "interleaved_contrast",
                "type_compare",
                f"{_front_instruction('Type the correct Spanish form')}<br>{sent1_front}<br><br>{_front_instruction('Then')}<br>{sent2_front}",
                f"{sent1_ans} | {sent2_ans}",
                f"1. {sent1_ans} — {sent1_note}<br>2. {sent2_ans} — {sent2_note}",
                f"Interleaved contrast: {topic_name}. Choose the right form for each context.",
                f"- {sent1_ans}<br>- {sent2_ans}",
            )
        )
    return cards


def _sentence_cards(audio_card_quotas=None):
    cards = []
    audio_card_quotas = audio_card_quotas or AUDIO_CARD_QUOTAS_BY_LEVEL
    pairs = _load_tatoeba_pairs()
    roles = _assign_sentence_roles(pairs, audio_card_quotas)
    used_sentence_ids = set()
    for index, row in enumerate(pairs, start=1):
        level = row["level"]
        topic = row["topic"]
        target = row["target"]
        spa_id = row["spa_id"]
        if spa_id in used_sentence_ids:
            continue
        spa_text = row["spa_text"]
        eng_id = row["eng_id"]
        eng_text = row["eng_text"]
        pattern = re.compile(TARGET_PATTERNS[target])
        cloze = pattern.sub("_____", spa_text, count=1)
        source = f"Tatoeba spa:{spa_id} eng:{eng_id}"
        attribution = TATOEBA_ATTRIBUTION.format(spa_id=spa_id, eng_id=eng_id)
        if spa_id not in roles:
            used_sentence_ids.add(spa_id)
            cards.append(
                _card(
                    f"tatoeba::{level}::{spa_id}::{eng_id}::{_slug(target)}",
                    level,
                    topic,
                    "typed_cloze",
                    "type_exact",
                    f"{_front_instruction('Complete the Spanish from context')}<br>{cloze}",
                    target,
                    "Type the missing Spanish word/chunk from the real sentence.",
                    "Real sentence cloze; retrieve the missing chunk from context.",
                    f"- {spa_text}<br>- {eng_text}",
                    source=source,
                    attribution=attribution,
                )
            )
        elif roles[spa_id] == "audio_cloze":
            used_sentence_ids.add(spa_id)
            url = _audio_url(spa_id)
            sound = f"[sound:tatoeba_spa_{spa_id}.mp3]"
            cards.append(
                _card(
                    f"tatoeba_audio::{level}::{spa_id}::{eng_id}::{_slug(target)}",
                    level,
                    "listening sentence mining",
                    "audio_cloze",
                    "type_exact",
                    f"{sound}<br><br>{_front_instruction('Listen first, then complete the chunk')}<br>{cloze}",
                    target,
                    "Listen first, type the missing chunk, then replay and shadow the full sentence once.",
                    "Audio cloze; retrieve from sound and context.",
                    f"- {spa_text}<br>- {eng_text}",
                    audio=sound,
                    audio_url=url,
                    audio_contributor=row.get("audio_contributor", "") or "Tatoeba contributor not listed in export",
                    audio_license=row.get("audio_license", "") or row.get("license", "") or TATOEBA_LICENSE,
                    audio_id=row.get("audio_id", ""),
                    source=source,
                    attribution=attribution,
                )
            )
    return cards


def build_cards(include_tatoeba=True):
    cards = []
    for topic in spanish_grammar_levels.TOPICS:
        cards.extend(_topic_cards(topic))
    cards.extend(_verb_paradigm_cards())
    cards.extend(_l1_l2_production_cards())
    cards.extend(_interleaved_contrast_cards())
    if include_tatoeba:
        cards.extend(_sentence_cards())
        cards.extend(_dictation_cards())
    return cards


def get_cards(level=None, card_type=None):
    cards = build_cards()
    if level is not None:
        cards = [card for card in cards if card["Level"] == level]
    if card_type is not None:
        cards = [card for card in cards if card["CardType"] == card_type]
    return cards


def get_level_summary():
    cards = build_cards()
    return [
        {
            "id": level["id"],
            "deck": level["deck"],
            "goal": level["goal"],
            "card_count": sum(1 for card in cards if card["Level"] == level["id"]),
        }
        for level in LEVELS
    ]


def validate_cards(cards):
    errors = []
    source_ids = [card["SourceID"] for card in cards]
    if len(source_ids) != len(set(source_ids)):
        dupes = [sid for sid in source_ids if source_ids.count(sid) > 1]
        errors.append(f"duplicate SourceID: {set(dupes)}")
    for card in cards:
        for field in ("SourceID", "DeckPath", "Level", "CardType", "PromptMode", "Front", "Answer", "Back"):
            if not card[field]:
                errors.append(f"{card['SourceID']}: blank {field}")
        if card["PromptMode"] == "type_exact" and len(card["Answer"].split()) > 4:
            errors.append(f"{card['SourceID']}: long answer marked type_exact")
        if card["CardType"] == "typed_cloze" and "_____" not in card["Front"]:
            errors.append(f"{card['SourceID']}: typed_cloze missing blank")
        if card["CardType"] == "typed_cloze":
            front_text = re.sub(r"<[^>]+>", " ", card["Front"]).replace("_____", " ")
            if re.search(rf"\b{re.escape(card['Answer'])}\b", front_text, flags=re.IGNORECASE):
                errors.append(f"{card['SourceID']}: typed_cloze answer leaks on front")
        if "{{c1::" in " ".join(card.values()):
            errors.append(f"{card['SourceID']}: legacy cloze marker")
    return errors


def render_tsv(cards):
    with io.StringIO() as output:
        output.write("#separator:tab\n")
        output.write("#html:true\n")
        writer = csv.DictWriter(output, delimiter="\t", lineterminator="\n", fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(cards)
        return output.getvalue()


def write_import_files(output_dir=OUTPUT_DIR):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    cards = get_cards()
    errors = validate_cards(cards)
    if errors:
        raise ValueError("\n".join(errors[:20]))
    path = output_path / "spanish_core_learning.tsv"
    path.write_text(render_tsv(cards), encoding="utf-8")
    return str(path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Generate Spanish Core Learning Anki TSV.")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--no-tatoeba", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.summary:
        for item in get_level_summary():
            print(f"{item['id']}: {item['card_count']} cards")
        print(f"total: {len(get_cards())} cards")
        return 0
    path = write_import_files(args.output_dir)
    print(f"Wrote import file: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
