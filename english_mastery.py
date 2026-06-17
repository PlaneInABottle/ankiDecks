import argparse
import bz2
import csv
import html
import io
import re
import tarfile
from pathlib import Path

import english_phrases
import grammar_levels


OUTPUT_DIR = Path("generated/english_mastery")
TATOEBA_DIR = Path("generated/sources/tatoeba")
TATOEBA_SELECTED_PATH = TATOEBA_DIR / "selected_eng_audio_sentences.tsv"

MODEL_NAME = "English Mastery"
TATOEBA_LICENSE = "Tatoeba sentence text/audio metadata from public export."
TATOEBA_ATTRIBUTION = "Source: Tatoeba.org English sentence ID {eng_id}."
INACCESSIBLE_AUDIO_SENTENCE_IDS = {"1294", "1305", "1355", "1361", "1380", "1394", "1419", "2053", "2206", "2228", "22447"}

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
    "Source",
    "Attribution",
    "Tags",
]

DECKS = {
    "b2": "English Mastery::B2 Grammar Control",
    "c1": "English Mastery::C1 Precision & Style",
    "c2": "English Mastery::C2 Native Usage",
    "phrase": "English Mastery::Natural Phrases",
    "listening": "English Mastery::Listening & Dictation",
}

PHRASE_PRODUCTION_LEVELS = {"level_2", "level_3", "level_4", "level_5", "level_6"}

LISTENING_TARGETS = [
    ("have been", r"\bhave been\b"),
    ("has been", r"\bhas been\b"),
    ("had", r"\bhad\b"),
    ("would have", r"\bwould have\b"),
    ("should have", r"\bshould have\b"),
    ("could have", r"\bcould have\b"),
    ("might have", r"\bmight have\b"),
    ("used to", r"\bused to\b"),
    ("even though", r"\beven though\b"),
    ("although", r"\balthough\b"),
    ("however", r"\bhowever\b"),
    ("therefore", r"\btherefore\b"),
    ("in fact", r"\bin fact\b"),
    ("for example", r"\bfor example\b"),
    ("as soon as", r"\bas soon as\b"),
    ("on the other hand", r"\bon the other hand\b"),
    ("at least", r"\bat least\b"),
    ("instead of", r"\binstead of\b"),
    ("as long as", r"\bas long as\b"),
    ("in order to", r"\bin order to\b"),
]


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _strip_html(text):
    return re.sub(r"<[^>]+>", "", str(text)).strip()


def _html_list(text):
    normalized = re.sub(r"\s+", " ", str(text)).strip()
    parts = [part.strip() for part in re.split(r"\s+\|\s+", normalized) if part.strip()]
    return "<br>".join(f"- {html.escape(part)}" for part in parts)


def _deck_for_level(level):
    if level.startswith("b2"):
        return DECKS["b2"]
    if level.startswith("c1"):
        return DECKS["c1"]
    if level.startswith("c2"):
        return DECKS["c2"]
    return DECKS["phrase"]


def _tags(level, topic, card_type):
    return " ".join(["english_mastery", level, _slug(topic), card_type])


def _card(
    source_id,
    deck_path,
    level,
    topic,
    card_type,
    prompt_mode,
    front,
    answer,
    back,
    formula="",
    examples="",
    audio="",
    audio_url="",
    source="",
    attribution="",
):
    type_answer = answer if prompt_mode in {"type_exact", "type_compare"} else ""
    return {
        "SourceID": source_id,
        "DeckPath": deck_path,
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
        "Source": source,
        "Attribution": attribution,
        "Tags": _tags(level, topic, card_type),
    }


def _blank_phrase(sentence, phrase):
    escaped = html.escape(sentence)
    phrase_pattern = re.escape(html.escape(phrase.strip()))
    if phrase.lower().startswith("to "):
        phrase_pattern = r"(?:to\s+)?" + re.escape(html.escape(phrase[3:].strip()))
    pattern = re.compile(phrase_pattern, re.IGNORECASE)
    if pattern.search(escaped):
        return pattern.sub("_____", escaped, count=1)
    words = [word for word in re.findall(r"[A-Za-z']+", phrase) if word.lower() not in {"to", "be", "a", "the"}]
    for word in sorted(words, key=len, reverse=True):
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        if pattern.search(escaped):
            return pattern.sub("_____", escaped, count=1)
    return escaped + "<br>Target phrase: _____"


def _phrase_cards():
    cards = []
    for item in english_phrases.load_cards():
        level = item["level"]
        phrase = item["phrase"]
        topic = "natural phrases"
        source_id = item["source_id"]
        cloze = _blank_phrase(item["front"], phrase)
        examples = _html_list(item["examples"])
        cards.append(
            _card(
                f"{source_id}::phrase_cloze",
                DECKS["phrase"],
                level,
                topic,
                "phrase_cloze",
                "type_exact" if len(phrase.split()) <= 4 else "type_compare",
                f"<b>Situation</b><br>{html.escape(item['meaning'])}<br><br><b>Complete naturally</b><br>{cloze}",
                phrase,
                f"{html.escape(phrase)} = {html.escape(item['meaning'])}",
                "Retrieve the full phrase from meaning and sentence context.",
                examples,
            )
        )
        if level in PHRASE_PRODUCTION_LEVELS:
            cards.append(
                _card(
                    f"{source_id}::phrase_production",
                    DECKS["phrase"],
                    level,
                    topic,
                    "phrase_production",
                    "type_compare",
                    f"Write one natural sentence for this situation using the target phrase:<br>{html.escape(item['meaning'])}",
                    item["front"],
                    f"Target phrase: <b>{html.escape(phrase)}</b><br>{html.escape(item['meaning'])}",
                    "Situation -> natural sentence using a formulaic sequence.",
                    examples,
                )
            )
    return cards


def _extract_answer(back):
    text = str(back)
    match = re.search(r"<b>(?:Correct|Answer)</b><br>(.*?)(?:<br><br><b>|$)", text, re.S)
    answer = _strip_html(match.group(1) if match else text)
    return re.sub(r"^[A-Z]\)\s*", "", answer).strip()


def _front_without_choices(front):
    text = re.sub(r"(?i)^choose(?: and explain| the better sequence| the meaning| the punctuation pattern)?:?\s*", "", front).strip()
    text = re.sub(r"<br>[A-Z]\)\s*[^<]+", "", text)
    text = text.replace("____.", "_____.")
    return text


def _grammar_formula(back):
    match = re.search(r"<b>Formula</b><br>(.*?)(?:<br><br><b>|$)", back, re.S)
    return match.group(1).strip() if match else ""


def _grammar_examples(back):
    match = re.search(r"<b>Examples</b><br>(.*?)(?:<br><br><b>|$)", back, re.S)
    return match.group(1).strip() if match else ""


def _grammar_cards():
    cards = []
    seen_topics = set()
    for index, item in enumerate(grammar_levels.get_cards(), start=1):
        level = item["level"]
        topic = item["topic"]
        deck = _deck_for_level(level)
        source_base = f"grammar::{level}::{_slug(topic)}::{index:03d}"
        answer = _extract_answer(item["back"])
        formula = _grammar_formula(item["back"])
        examples = _grammar_examples(item["back"])
        reason = _strip_html(item.get("reason") or item["back"])
        if topic not in seen_topics:
            seen_topics.add(topic)
            cards.append(
                _card(
                    f"grammar_rule::{level}::{_slug(topic)}",
                    deck,
                    level,
                    topic,
                    "rule",
                    "self_grade",
                    f"Rule anchor: {topic}",
                    formula or topic,
                    reason,
                    formula,
                    examples,
                )
            )
        front = item["front"]
        if front.lower().startswith("correct:"):
            card_type = "typed_correction"
            prompt = front.replace("Correct:", "Correct the sentence:", 1)
            prompt_mode = "type_compare"
        elif front.lower().startswith(("make ", "say ", "express ", "avoid ", "join ", "use ")):
            card_type = "typed_production"
            prompt = front
            prompt_mode = "type_compare"
        else:
            card_type = "typed_contrast"
            prompt = "Type the correct/natural English form:<br>" + _front_without_choices(front)
            prompt_mode = "type_exact" if len(answer.split()) <= 8 else "type_compare"
        cards.append(
            _card(
                f"{source_base}::{card_type}",
                deck,
                level,
                topic,
                card_type,
                prompt_mode,
                prompt,
                answer,
                reason,
                formula,
                examples,
            )
        )
    return cards


def _word_count(sentence):
    return len(re.findall(r"[A-Za-z']+", sentence))


def _is_clean_english_sentence(sentence):
    if any(marker in sentence for marker in ("@", "http://", "https://", "\t", "{", "}", "<", ">")):
        return False
    if sentence.count('"') > 2 or sentence.count(";") > 1:
        return False
    return 5 <= _word_count(sentence) <= 13


def _load_audio_metadata():
    path = TATOEBA_DIR / "sentences_with_audio.tar.bz2"
    rows = {}
    if not path.exists():
        return rows
    with tarfile.open(path, "r:bz2") as archive:
        handle = archive.extractfile("sentences_with_audio.csv")
        if handle is None:
            return rows
        reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8", newline=""), delimiter="\t")
        for row in reader:
            if len(row) >= 2:
                rows[row[0]] = row[1]
    return rows


def _load_english_audio_sentences():
    if TATOEBA_SELECTED_PATH.exists():
        with TATOEBA_SELECTED_PATH.open(encoding="utf-8", newline="") as handle:
            return [
                row
                for row in csv.DictReader(handle, delimiter="\t")
                if row["eng_id"] not in INACCESSIBLE_AUDIO_SENTENCE_IDS
            ]
    sentence_path = TATOEBA_DIR / "eng_sentences.tsv.bz2"
    audio = _load_audio_metadata()
    selected = []
    used = set()
    target_counts = {target: 0 for target, _ in LISTENING_TARGETS}
    target_patterns = [(target, re.compile(pattern, re.IGNORECASE)) for target, pattern in LISTENING_TARGETS]
    with bz2.open(sentence_path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) < 3:
                continue
            sent_id, lang, text = row[0], row[1], row[2]
            if lang != "eng" or sent_id not in audio or sent_id in INACCESSIBLE_AUDIO_SENTENCE_IDS or not _is_clean_english_sentence(text):
                continue
            for target, pattern in target_patterns:
                if target_counts[target] >= 8 or sent_id in used:
                    continue
                if pattern.search(text):
                    selected.append({"eng_id": sent_id, "text": text, "target": target, "audio_id": audio[sent_id], "kind": "audio_cloze"})
                    target_counts[target] += 1
                    used.add(sent_id)
                    break
            if len([row for row in selected if row["kind"] == "audio_cloze"]) >= 120:
                break
    with bz2.open(sentence_path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) < 3:
                continue
            sent_id, lang, text = row[0], row[1], row[2]
            if len([row for row in selected if row["kind"] == "dictation"]) >= 60:
                break
            if (
                lang == "eng"
                and sent_id in audio
                and sent_id not in used
                and sent_id not in INACCESSIBLE_AUDIO_SENTENCE_IDS
                and _is_clean_english_sentence(text)
            ):
                selected.append({"eng_id": sent_id, "text": text, "target": text, "audio_id": audio[sent_id], "kind": "dictation"})
                used.add(sent_id)
    TATOEBA_SELECTED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TATOEBA_SELECTED_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", lineterminator="\n", fieldnames=["eng_id", "text", "target", "audio_id", "kind"])
        writer.writeheader()
        writer.writerows(selected)
    return selected


def _audio_url(eng_id):
    return f"https://audio.tatoeba.org/sentences/eng/{eng_id}.mp3"


def _listening_cards():
    cards = []
    for row in _load_english_audio_sentences():
        eng_id = row["eng_id"]
        text = row["text"]
        target = row["target"]
        sound = f"[sound:tatoeba_eng_{eng_id}.mp3]"
        source = f"Tatoeba eng:{eng_id}"
        attribution = TATOEBA_ATTRIBUTION.format(eng_id=eng_id)
        if row["kind"] == "audio_cloze":
            pattern = re.compile(re.escape(target), re.IGNORECASE)
            cloze = pattern.sub("_____", html.escape(text), count=1)
            cards.append(
                _card(
                    f"tatoeba_eng_audio::{eng_id}::{_slug(target)}",
                    DECKS["listening"],
                    "listening",
                    "listening sentence mining",
                    "audio_cloze",
                    "type_exact",
                    f"{sound}<br><br>Listen first, then complete the chunk:<br>{cloze}",
                    target,
                    "Replay once and shadow the full sentence.",
                    "Audio cloze; retrieve the missing chunk from sound and sentence context.",
                    f"- {html.escape(text)}",
                    audio=sound,
                    audio_url=_audio_url(eng_id),
                    source=source,
                    attribution=attribution,
                )
            )
        else:
            cards.append(
                _card(
                    f"tatoeba_eng_dictation::{eng_id}",
                    DECKS["listening"],
                    "listening",
                    "short dictation",
                    "dictation",
                    "type_compare",
                    f"{sound}<br><br>Type the full sentence you hear.",
                    text,
                    "Compare punctuation and weak forms, then replay once.",
                    "Short dictation for word boundaries and spelling.",
                    f"- {html.escape(text)}",
                    audio=sound,
                    audio_url=_audio_url(eng_id),
                    source=source,
                    attribution=attribution,
                )
            )
    return cards


def build_cards(include_listening=True):
    cards = []
    cards.extend(_phrase_cards())
    cards.extend(_grammar_cards())
    if include_listening:
        cards.extend(_listening_cards())
    return cards


def get_cards(level=None, card_type=None):
    cards = build_cards()
    if level is not None:
        cards = [card for card in cards if card["Level"] == level]
    if card_type is not None:
        cards = [card for card in cards if card["CardType"] == card_type]
    return cards


def validate_cards(cards):
    errors = []
    source_ids = [card["SourceID"] for card in cards]
    if len(source_ids) != len(set(source_ids)):
        errors.append("duplicate SourceID")
    for card in cards:
        for field in ("SourceID", "DeckPath", "Level", "Topic", "CardType", "PromptMode", "Front", "Answer", "Back"):
            if not card[field]:
                errors.append(f"{card['SourceID']}: blank {field}")
        if card["PromptMode"].startswith("type_") and card["TypeAnswer"] != card["Answer"]:
            errors.append(f"{card['SourceID']}: TypeAnswer mismatch")
        if card["CardType"] in {"phrase_cloze", "typed_contrast", "audio_cloze"} and (
            "A)" in card["Front"] or "B)" in card["Front"]
        ):
            errors.append(f"{card['SourceID']}: multiple-choice marker")
        if card["CardType"] == "phrase_cloze" and card["Answer"].lower() in card["Front"].lower().replace("_____", ""):
            errors.append(f"{card['SourceID']}: phrase answer leaks on front")
        if card["Topic"] == "natural phrases" and card["Examples"].count("<br>") > 2:
            errors.append(f"{card['SourceID']}: too many phrase example fragments")
    return errors


def render_tsv(cards):
    with io.StringIO() as output:
        output.write("#separator:tab\n#html:true\n")
        writer = csv.DictWriter(output, delimiter="\t", lineterminator="\n", fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(cards)
        return output.getvalue()


def write_import_file(output_dir=OUTPUT_DIR):
    cards = build_cards()
    errors = validate_cards(cards)
    if errors:
        raise ValueError("\n".join(errors[:30]))
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    path = output_path / "english_mastery.tsv"
    path.write_text(render_tsv(cards), encoding="utf-8")
    return str(path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Generate English Mastery Anki TSV.")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--summary", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.summary:
        from collections import Counter

        cards = build_cards()
        print(f"total: {len(cards)}")
        print("by type:", dict(Counter(card["CardType"] for card in cards)))
        print("by deck:", dict(Counter(card["DeckPath"] for card in cards)))
        return 0
    print(f"Wrote import file: {write_import_file(args.output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
