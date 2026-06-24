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
    "SelfGrade",
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
    ("in spite of", r"\bin spite of\b"),
    ("despite", r"\bdespite\b"),
    ("rather than", r"\brather than\b"),
    ("by the time", r"\bby the time\b"),
    ("so that", r"\bso that\b"),
    ("in case", r"\bin case\b"),
    ("unless", r"\bunless\b"),
    ("provided that", r"\bprovided that\b"),
    ("even if", r"\beven if\b"),
    ("no matter", r"\bno matter\b"),
    ("nevertheless", r"\bnevertheless\b"),
    ("moreover", r"\bmoreover\b"),
    ("furthermore", r"\bfurthermore\b"),
    ("consequently", r"\bconsequently\b"),
    ("meanwhile", r"\bmeanwhile\b"),
    ("indeed", r"\bindeed\b"),
    ("obviously", r"\bobviously\b"),
    ("fortunately", r"\bfortunately\b"),
    ("unfortunately", r"\bunfortunately\b"),
    ("generally", r"\bgenerally\b"),
]

SENTENCE_MINING_TARGETS = [
    ("b2_tense_system", "have been", r"\bhave been\b"),
    ("b2_tense_system", "has been", r"\bhas been\b"),
    ("b2_tense_system", "had", r"\bhad\b"),
    ("b2_tense_system", "would have", r"\bwould have\b"),
    ("b2_tense_system", "should have", r"\bshould have\b"),
    ("b2_tense_system", "could have", r"\bcould have\b"),
    ("b2_tense_system", "used to", r"\bused to\b"),
    ("b2_tense_system", "will have", r"\bwill have\b"),
    ("b2_sentence_control", "if I had", r"\bif I had\b"),
    ("b2_sentence_control", "if I were", r"\bif I were\b"),
    ("b2_sentence_control", "I would have", r"\bI would have\b"),
    ("b2_sentence_control", "was being", r"\bwas being\b"),
    ("b2_sentence_control", "were being", r"\bwere being\b"),
    ("b2_sentence_control", "has been being", r"\bhas been being\b"),
    ("b2_verb_patterns", "used to", r"\bused to\b"),
    ("b2_verb_patterns", "is used to", r"\bis used to\b"),
    ("b2_verb_patterns", "get used to", r"\bget used to\b"),
    ("b2_verb_patterns", "had better", r"\bhad better\b"),
    ("b2_verb_patterns", "would rather", r"\bwould rather\b"),
    ("c1_precision", "in spite of", r"\bin spite of\b"),
    ("c1_precision", "despite", r"\bdespite\b"),
    ("c1_precision", "rather than", r"\brather than\b"),
    ("c1_precision", "by the time", r"\bby the time\b"),
    ("c1_precision", "so that", r"\bso that\b"),
    ("c1_precision", "in case", r"\bin case\b"),
    ("c1_precision", "unless", r"\bunless\b"),
    ("c1_precision", "provided that", r"\bprovided that\b"),
    ("c1_precision", "as long as", r"\bas long as\b"),
    ("c1_precision", "even if", r"\beven if\b"),
    ("c1_precision", "no matter", r"\bno matter\b"),
    ("c1_style", "nevertheless", r"\bnevertheless\b"),
    ("c1_style", "moreover", r"\bmoreover\b"),
    ("c1_style", "furthermore", r"\bfurthermore\b"),
    ("c1_style", "consequently", r"\bconsequently\b"),
    ("c1_style", "meanwhile", r"\bmeanwhile\b"),
    ("c1_style", "indeed", r"\bindeed\b"),
    ("c1_style", "obviously", r"\bobviously\b"),
    ("c1_style", "fortunately", r"\bfortunately\b"),
    ("c1_style", "unfortunately", r"\bunfortunately\b"),
    ("c2_mastery", "not only", r"\bnot only\b"),
    ("c2_mastery", "it is", r"\bit is .{1,30} that\b"),
    ("c2_mastery", "what is", r"\bwhat is .{1,30} is\b"),
    ("c2_mastery", "the fact that", r"\bthe fact that\b"),
    ("c2_mastery", "regardless of", r"\bregardless of\b"),
    ("c2_mastery", "owing to", r"\bowing to\b"),
    ("c2_mastery", "apart from", r"\bapart from\b"),
    ("c2_mastery", "in light of", r"\bin light of\b"),
]

SENTENCE_MINING_PER_TARGET = 3

TARGET_CUES = {
    "have been": "perfect auxiliary for duration/state",
    "has been": "perfect auxiliary for duration/state",
    "had": "base verb idea: have / possess",
    "would have": "unreal past result chunk",
    "should have": "past advice or criticism chunk",
    "could have": "past possibility or ability chunk",
    "might have": "past possibility chunk",
    "used to": "past habit marker",
    "will have": "future perfect auxiliary chunk",
    "if I had": "unreal past condition opener",
    "if I were": "hypothetical condition opener",
    "I would have": "unreal past result opener",
    "was being": "past continuous passive auxiliary",
    "were being": "past continuous passive auxiliary",
    "has been being": "perfect continuous passive auxiliary",
    "is used to": "be accustomed to",
    "get used to": "become accustomed to",
    "had better": "strong advice chunk",
    "would rather": "preference chunk",
    "in spite of": "concession: although this is true",
    "despite": "concession: although this is true",
    "rather than": "alternative: instead of",
    "by the time": "time limit before another event",
    "so that": "purpose clause connector",
    "in case": "precaution connector",
    "unless": "condition: if not",
    "provided that": "condition: only if",
    "as long as": "condition: only if",
    "even if": "concession with hypothetical condition",
    "no matter": "concession: it does not matter which/how",
    "nevertheless": "contrast: despite that",
    "moreover": "addition: another stronger point",
    "furthermore": "addition: another supporting point",
    "consequently": "result connector",
    "meanwhile": "same-time contrast/sequence connector",
    "indeed": "emphasis or confirmation",
    "obviously": "certainty stance adverb",
    "fortunately": "positive outcome stance adverb",
    "unfortunately": "negative outcome stance adverb",
    "not only": "emphatic addition opener",
    "it is": "cleft emphasis opener",
    "what is": "cleft focus opener",
    "the fact that": "nominal clause opener",
    "regardless of": "concession: not affected by",
    "owing to": "cause connector",
    "apart from": "exception or addition connector",
    "in light of": "reason/context connector",
}


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


def _target_cue(target):
    return TARGET_CUES.get(target, f"target idea: {target}")


def _front_instruction(text):
    return f'<span class="front-instruction">{html.escape(text)}</span>'


def _front_label(text):
    return f'<span class="front-label">{html.escape(text)}</span>'


def _front_cue(label, text):
    return f'<span class="front-cue">{_front_label(label)}: {html.escape(text)}</span>'


def _strip_trailing_period(text, keep_for_dictation=False):
    if keep_for_dictation:
        return text
    return re.sub(r"\.+$", "", text.rstrip())


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
    self_grade="",
):
    answer = _strip_trailing_period(answer, keep_for_dictation=card_type == "dictation")
    if card_type == "rule" and formula.strip() == answer:
        formula = ""
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
        "SelfGrade": self_grade,
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
                f'<span class="front-cue">{_front_label("Meaning cue")}<br>{html.escape(item["meaning"])}</span><br><br>{_front_instruction("Complete naturally")}<br>{cloze}',
                phrase,
                html.escape(item["meaning"]),
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
                "self_grade",
                f'{_front_instruction("Produce one natural sentence using the target phrase, then compare for naturalness")}<br>{html.escape(item["meaning"])}',
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
    text = re.sub(r"<br>Cue:\s*[^<]+", "", text, flags=re.I)
    text = re.sub(r"<br>[A-Z]\)\s*[^<]+", "", text)
    text = re.sub(r"_{3,}", "_____", text)
    return text


CONTENT_LEMMAS = {
    "reviewed": "review",
    "lived": "live",
    "took": "take",
    "crashed": "crash",
    "applied": "apply",
    "finished": "finish",
    "having": "have",
    "editing": "edit",
    "noticed": "notice",
    "cleared": "clear",
    "eaten": "eat",
    "left": "leave",
    "written": "write",
    "rains": "rain",
    "rained": "rain",
    "approved": "approve",
    "playing": "play",
    "waking": "wake up",
    "translated": "translate",
    "responsible": "responsible",
    "submitted": "submit",
    "working": "work",
    "proposed": "propose",
    "promoted": "promote",
    "effective": "effective",
    "isolated": "isolated",
    "incident": "incident",
    "beautifully": "beautifully",
    "detailed": "detailed",
    "encrypted": "encrypt",
    "receive": "receive",
    "compensation": "compensation",
    "worried": "worry",
    "delay": "delay",
    "accepted": "accept",
    "rejected": "reject",
    "proposal": "proposal",
    "costly": "costly",
    "carefully": "carefully",
    "tested": "test",
    "building": "build",
    "maintaining": "maintain",
}

FUNCTION_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "been",
    "being",
    "by",
    "did",
    "do",
    "does",
    "for",
    "had",
    "has",
    "have",
    "if",
    "in",
    "is",
    "it",
    "not",
    "of",
    "on",
    "should",
    "than",
    "that",
    "the",
    "they",
    "to",
    "was",
    "were",
    "will",
    "with",
    "would",
}


def _missing_chunk_from_front_answer(front, answer):
    front_text = re.sub(r"<br\s*/?>", "\n", front, flags=re.IGNORECASE)
    front_text = _strip_html(front_text)
    lines = [line.strip() for line in front_text.splitlines() if line.strip()]
    lines = [
        line
        for line in lines
        if line.lower() not in {"type the correct/natural english form", "then"}
        and not line.lower().startswith("target cue")
    ]
    front_text = "\n".join(lines)
    parts = re.split(r"_{3,}", front_text, maxsplit=1)
    if len(parts) != 2:
        return ""
    before, after = (part.strip() for part in parts)
    answer_text = _strip_html(answer).strip()
    if before and answer_text.lower().startswith(before.lower()):
        answer_text = answer_text[len(before):].strip()
    if after:
        after_variants = [after, after.rstrip(" .;:!?")]
        for after_variant in after_variants:
            if after_variant and answer_text.lower().endswith(after_variant.lower()):
                answer_text = answer_text[: -len(after_variant)].strip()
                break
    return answer_text.strip(" ,.;:!?")


def _lexical_cue_from_chunk(chunk):
    words = re.findall(r"[A-Za-z']+", chunk)
    content = [word for word in words if word.lower() not in FUNCTION_WORDS]
    if not content:
        return ""
    return " / ".join(_lemma_for_cue(word) for word in content[:2])


def _lemma_for_cue(word):
    lowered = word.lower()
    if lowered in CONTENT_LEMMAS:
        return CONTENT_LEMMAS[lowered]
    if lowered.endswith("ied") and len(lowered) > 4:
        return lowered[:-3] + "y"
    if lowered.endswith("ing") and len(lowered) > 5:
        stem = lowered[:-3]
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if lowered.endswith("ed") and len(lowered) > 4:
        stem = lowered[:-2]
        if stem.endswith(("at", "iz", "iv", "ur")):
            return stem + "e"
        return stem
    if lowered.endswith("s") and len(lowered) > 3:
        return lowered[:-1]
    return lowered


def _cue_for_missing_chunk(chunk, topic="", formula=""):
    cue = _lexical_cue_from_chunk(chunk)
    if cue:
        return "Target cue", cue
    pattern = topic.strip() or formula.strip() or "grammar pattern"
    return "Pattern cue", pattern


def _prompt_with_required_cue(prompt, chunk, topic="", formula=""):
    cue_label, cue = _cue_for_missing_chunk(chunk, topic, formula)
    return f"{prompt}<br><br>{_front_cue(cue_label, cue)}"


def _grammar_formula(back):
    match = re.search(r"<b>Formula</b><br>(.*?)(?:<br><br><b>|$)", back, re.S)
    return match.group(1).strip() if match else ""


def _grammar_examples(back):
    match = re.search(r"<b>Examples</b><br>(.*?)(?:<br><br><b>|$)", back, re.S)
    return match.group(1).strip() if match else ""


def _grammar_self_grade(back):
    match = re.search(r"<b>Self-Grade</b><br>(.*?)(?:<br><br><b>|$)", back, re.S)
    return _strip_html(match.group(1)) if match else ""


def _grammar_reason(back):
    reason = re.sub(r"<br><br><b>Examples</b><br>.*?(?=<br><br><b>|$)", "", back, flags=re.S)
    reason = re.sub(r"<br><br><b>Self-Grade</b><br>.*?(?=<br><br><b>|$)", "", reason, flags=re.S)
    return _strip_html(reason)


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
        self_grade = _grammar_self_grade(item.get("reason") or item["back"])
        reason = _grammar_reason(item.get("reason") or item["back"])
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
                    f'{_front_instruction("Rule anchor")}<br>{html.escape(topic)}',
                    formula or topic,
                    reason,
                    formula,
                    examples,
                    self_grade=self_grade,
                )
            )
        front = item["front"]
        if front.lower().startswith("correct:"):
            card_type = "typed_correction"
            prompt = front.replace("Correct:", f'{_front_instruction("Correct the sentence")}:', 1)
            prompt_mode = "type_compare"
        elif front.lower().startswith(("make ", "say ", "express ", "avoid ", "join ", "use ")):
            card_type = "typed_production"
            prompt = front
            prompt_mode = "type_compare"
        else:
            card_type = "typed_contrast"
            prompt_base = _front_instruction("Type the correct/natural English form") + "<br>" + _front_without_choices(front)
            missing_answer = _missing_chunk_from_front_answer(prompt_base, answer)
            answer_for_card = missing_answer or answer
            prompt = _prompt_with_required_cue(prompt_base, answer_for_card, topic, formula)
            prompt_mode = "type_exact" if len(answer_for_card.split()) <= 5 else "type_compare"
            if answer_for_card != answer:
                reason = f"{reason}<br><br>Full sentence: {html.escape(answer)}"
            answer = answer_for_card
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
                self_grade=self_grade,
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
                if target_counts[target] >= 3 or sent_id in used:
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


def _load_sentence_mining_sentences():
    """Mine Tatoeba English sentences for grammar pattern cloze cards."""
    cache_path = TATOEBA_DIR / "selected_eng_mining_sentences.tsv"
    reserved_audio_ids = {row["eng_id"] for row in _load_english_audio_sentences()}
    if cache_path.exists():
        with cache_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        if not any(row["eng_id"] in reserved_audio_ids for row in rows):
            return rows
    sentence_path = TATOEBA_DIR / "eng_sentences.tsv.bz2"
    audio = _load_audio_metadata()
    selected = []
    used = set(reserved_audio_ids)
    target_counts = {(level, target): 0 for level, target, _ in SENTENCE_MINING_TARGETS}
    target_patterns = [(level, target, re.compile(pattern, re.IGNORECASE)) for level, target, pattern in SENTENCE_MINING_TARGETS]
    with bz2.open(sentence_path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) < 3:
                continue
            sent_id, lang, text = row[0], row[1], row[2]
            if lang != "eng" or not _is_clean_english_sentence(text) or sent_id in used:
                continue
            for level, target, pattern in target_patterns:
                key = (level, target)
                if target_counts[key] >= SENTENCE_MINING_PER_TARGET:
                    continue
                if pattern.search(text):
                    has_audio = sent_id in audio and sent_id not in INACCESSIBLE_AUDIO_SENTENCE_IDS
                    selected.append({
                        "eng_id": sent_id,
                        "text": text,
                        "target": target,
                        "level": level,
                        "audio_id": audio.get(sent_id, ""),
                        "has_audio": has_audio,
                    })
                    target_counts[key] += 1
                    used.add(sent_id)
                    break
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", lineterminator="\n",
                                fieldnames=["eng_id", "text", "target", "level", "audio_id", "has_audio"])
        writer.writeheader()
        writer.writerows(selected)
    return selected


def _sentence_mining_cards():
    """Create typed_cloze cards from real Tatoeba English sentences."""
    cards = []
    for row in _load_sentence_mining_sentences():
        eng_id = row["eng_id"]
        text = row["text"]
        target = row["target"]
        level = row["level"]
        deck = _deck_for_level(level)
        pattern = re.compile(re.escape(target), re.IGNORECASE)
        cloze = pattern.sub("_____", html.escape(text), count=1)
        source = f"Tatoeba eng:{eng_id}"
        attribution = TATOEBA_ATTRIBUTION.format(eng_id=eng_id)
        cards.append(
            _card(
                f"tatoeba_eng_mining::{level}::{eng_id}::{_slug(target)}",
                deck,
                level,
                "sentence mining",
                "typed_cloze",
                "type_exact",
                f'{_front_instruction("Complete the English from context")}<br>{_front_cue("Target cue", _target_cue(target))}<br><br>{cloze}',
                target,
                "Type the missing chunk from the real sentence.",
                "Real sentence cloze; retrieve the missing chunk from context.",
                f"- {html.escape(text)}",
                source=source,
                attribution=attribution,
            )
        )
    return cards


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
                    f'{sound}<br><br>{_front_instruction("Listen first, then complete the chunk")}<br>{cloze}',
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
                    f'{sound}<br><br>{_front_instruction("Type the full sentence you hear")}',
                    text,
                    "Compare punctuation and weak forms, then replay once.",
                    "Short dictation for word boundaries and spelling.",
                    "",
                    audio=sound,
                    audio_url=_audio_url(eng_id),
                    source=source,
                    attribution=attribution,
                )
            )
    return cards


ENGLISH_INTERLEAVED_CONTRASTS = [
    ("b2_tense_system", "present perfect vs past simple",
     "I _____ in London since 2018.", "I have lived in London since 2018", "present perfect: unfinished time (since)",
     "I _____ in London in 2018.", "I lived in London in 2018", "past simple: finished time (in)"),
    ("b2_tense_system", "present perfect vs past simple (experience)",
     "Have you ever _____ sushi?", "Have you ever eaten sushi", "present perfect: life experience (ever)",
     "Did you _____ sushi last night?", "Did you eat sushi last night", "past simple: specific past time"),
    ("b2_tense_system", "past perfect vs past simple",
     "By the time we arrived, they _____ already _____.", "By the time we arrived, they had already left", "past perfect: earlier event",
     "When we arrived, they _____ already _____.", "When we arrived, they already left", "past simple: sequential events"),
    ("b2_tense_system", "present perfect continuous vs present perfect",
     "I _____ for two hours.", "I have been waiting for two hours", "present perfect continuous: ongoing action + duration",
     "I _____ three emails today.", "I have written three emails today", "present perfect: completed count + today"),
    ("b2_tense_system", "will vs be going to",
     "Look at those clouds. It _____ rain.", "Look at those clouds. It is going to rain", "be going to: prediction from present evidence",
     "I think it _____ rain tomorrow.", "I think it will rain tomorrow", "will: prediction/opinion"),
    ("b2_sentence_control", "second vs third conditional",
     "If I _____ time, I would travel.", "If I had time, I would travel", "second conditional: unreal present/future",
     "If I _____ time, I would have traveled.", "If I had had time, I would have traveled", "third conditional: unreal past"),
    ("b2_sentence_control", "first vs second conditional",
     "If it _____ this weekend, we will cancel the trip.", "If it rains this weekend, we will cancel the trip", "first conditional: real future possibility",
     "If it _____ this weekend, we would cancel the trip.", "If it rained this weekend, we would cancel the trip", "second conditional: unreal/hypothetical"),
    ("b2_sentence_control", "passive vs active",
     "The report _____ by the editor yesterday.", "The report was reviewed by the editor yesterday", "passive: focus on receiver of action",
     "The editor _____ the report yesterday.", "The editor reviewed the report yesterday", "active: focus on doer"),
    ("b2_verb_patterns", "used to vs be used to",
     "I _____ play tennis every weekend.", "I used to play tennis every weekend", "used to + infinitive: past habit",
     "I _____ playing tennis every weekend.", "I am used to playing tennis every weekend", "be used to + gerund: accustomed to"),
    ("b2_verb_patterns", "used to vs get used to",
     "I _____ early as a child.", "I used to wake up early as a child", "used to: past habit",
     "I'm _____ waking up early.", "I'm getting used to waking up early", "get used to: process of becoming accustomed"),
    ("b2_verb_patterns", "had better vs would rather",
     "You _____ see a doctor.", "You had better see a doctor", "had better + infinitive: strong advice",
     "I _____ stay home.", "I would rather stay home", "would rather + infinitive: preference"),
    ("c1_precision", "despite vs in spite of",
     "_____ the rain, we went out.", "Despite the rain, we went out", "despite + noun (more formal)",
     "_____ of the rain, we went out.", "In spite of the rain, we went out", "in spite of + noun (slightly less formal)"),
    ("c1_precision", "unless vs if not",
     "_____ you hurry, you will miss the train.", "Unless you hurry, you will miss the train", "unless = if not (more concise, formal)",
     "_____ you do not hurry, you will miss the train.", "If you do not hurry, you will miss the train", "if not = explicit condition"),
    ("c1_precision", "so that vs in order to",
     "I left early _____ I could catch the train.", "I left early so that I could catch the train", "so that + clause (subject + verb)",
     "I left early _____ catch the train.", "I left early in order to catch the train", "in order to + infinitive (no subject)"),
    ("c1_style", "nevertheless vs however",
     "The report was late; _____, it was thorough.", "The report was late; nevertheless, it was thorough", "nevertheless: formal concession, stronger",
     "The report was late. _____, it was thorough.", "The report was late. However, it was thorough", "however: general contrast, softer"),
    ("c1_style", "furthermore vs moreover",
     "The system is fast. _____, it is secure.", "The system is fast. Furthermore, it is secure", "furthermore: adds a supporting point",
     "The system is fast. _____, it handles edge cases well.", "The system is fast. Moreover, it handles edge cases well", "moreover: adds a stronger/additional point"),
    ("c2_mastery", "not only inversion vs standard",
     "Not only _____ the report, but he also improved the process.", "Not only did he approve the report, but he also improved the process", "inversion after not only (formal, emphatic)",
     "He _____ approved the report but also improved the process.", "He not only approved the report but also improved the process", "standard word order (no inversion)"),
    ("c2_mastery", "it-cleft vs standard",
     "_____ timing that changed quality most.", "It was timing that changed quality most", "it-cleft: emphasis via structure",
     "_____ changed quality most.", "Timing changed quality most", "standard: subject + verb"),
    ("c2_mastery", "subjunctive vs indicative (mandative)",
     "The policy requires that every file _____ encrypted.", "The policy requires that every file be encrypted", "subjunctive: base form after require that (formal)",
     "The policy requires that every file _____ encrypted.", "The policy requires that every file is encrypted", "indicative: standard present (informal)"),
    ("c2_mastery", "parallelism vs broken parallelism",
     "Our goal is to plan, build, and _____ quality.", "Our goal is to plan, build, and maintain quality", "parallel: all base verbs after to",
     "Our goal is planning, building, and _____ quality.", "Our goal is planning, building, and maintaining quality", "parallel: all gerunds"),
]


def _interleaved_contrast_cards():
    """Cards that mix two competing English patterns for B2-C2 discrimination."""
    cards = []
    for level, topic_name, sent1_front, sent1_ans, sent1_note, sent2_front, sent2_ans, sent2_note in ENGLISH_INTERLEAVED_CONTRASTS:
        deck = _deck_for_level(level)
        sent1_chunk = _missing_chunk_from_front_answer(sent1_front, sent1_ans) or sent1_ans
        sent2_chunk = _missing_chunk_from_front_answer(sent2_front, sent2_ans) or sent2_ans
        cue1_label, cue1 = _cue_for_missing_chunk(sent1_chunk, topic_name)
        cue2_label, cue2 = _cue_for_missing_chunk(sent2_chunk, topic_name)
        cards.append(
            _card(
                f"interleaved::{level}::{_slug(topic_name)}::1",
                deck,
                level,
                topic_name,
                "interleaved_contrast",
                "type_compare",
                f'{_front_instruction("Type the correct/natural English form")}<br>{sent1_front}<br>{_front_cue(cue1_label, cue1)}<br><br>{_front_instruction("Then")}<br>{sent2_front}<br>{_front_cue(cue2_label, cue2)}',
                f"{sent1_chunk} | {sent2_chunk}",
                f"1. {html.escape(sent1_ans)} — {sent1_note}<br>2. {html.escape(sent2_ans)} — {sent2_note}",
                f"Interleaved contrast: {topic_name}. Choose the right form for each context.",
                "",
            )
        )
    return cards


def build_cards(include_listening=True, include_mining=True):
    cards = []
    cards.extend(_phrase_cards())
    cards.extend(_grammar_cards())
    cards.extend(_interleaved_contrast_cards())
    if include_mining:
        cards.extend(_sentence_mining_cards())
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
