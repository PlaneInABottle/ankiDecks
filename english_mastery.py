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
REJECT_SENTENCE_MINING_IDS = {
    # Low-value "had" possession examples; they do not train the B2 tense/grammar target.
    "1369",
    "1928",
    "1933",
    # Duplicate/less natural "get used to" examples; keep the cleaner travel-abroad example.
    "21852",
    "21891",
    # "is used to improve" means "is utilized to improve", not "is accustomed to".
    "35858",
    # Low-value/unnatural passive context: "Home life was being screened from foreign eyes."
    "24040",
    # Awkward passive context: "the demonstration was being made."
    "39314",
    # Ungrammatical/unnatural source sentence: "applicants must be woman."
    "246200",
    # Distracting story context for a simple by-the-time card.
    "17878",
    # Distracting/low-value source sentence for a connector card.
    "29672",
    # Incomplete source sentence ending in "but..."
    "264574",
    # "Meanwhile I can make myself understood" is not a useful same-time contrast card.
    "2164985",
    # Distracting/low-value source sentence for a connector card.
    "3464550",
}
REJECT_AUDIO_SENTENCE_IDS = {
    # Too little learning value: tests only simple possession "had".
    "2037",
}

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


def _front_cue_lines(cues):
    return "<br>".join(_front_cue(label, text) for label, text in cues if text)


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
    "gone": "go",
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
    "process": "process",
    "timing": "timing",
}

EXACT_ANSWER_BASE_CUES = {
    "advice": "advise -> noun",
    "although": "concession connector",
    "because": "reason connector",
    "check": "inspect / verify",
    "ensure": "make sure",
    "every": "each / all singular",
    "failure": "fail -> noun",
    "fewer": "few -> comparative",
    "important": "importance -> adjective",
    "information": "inform -> noun",
    "maintain": "keep / continue",
    "one": "substitute noun",
    "only": "contrast focus",
    "possibly": "possible -> adverb",
    "recommendation": "recommend -> noun",
    "reliable": "rely -> adjective",
    "review": "examine / check",
    "rich": "wealthy group",
    "therefore": "result connector",
    "though": "concession inversion",
    "what": "focus clause starter",
    "where": "place relative pronoun",
    "who": "person relative pronoun",
    "whose": "possession relative pronoun",
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
    "can",
    "could",
    "despite",
    "did",
    "do",
    "does",
    "for",
    "furthermore",
    "get",
    "getting",
    "got",
    "had",
    "has",
    "have",
    "however",
    "if",
    "in",
    "is",
    "it",
    "may",
    "might",
    "moreover",
    "must",
    "mustn't",
    "nevertheless",
    "not",
    "of",
    "on",
    "shall",
    "should",
    "spite",
    "than",
    "that",
    "the",
    "they",
    "to",
    "unless",
    "was",
    "were",
    "whether",
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
    if lowered.endswith("s") and len(lowered) > 3 and not lowered.endswith(("ss", "us", "is")):
        return lowered[:-1]
    return lowered


def _cue_for_missing_chunk(chunk, topic="", formula=""):
    cue = _lexical_cue_from_chunk(chunk)
    if cue:
        return "Target cue", cue
    pattern = topic.strip() or formula.strip() or "grammar pattern"
    return "Pattern cue", pattern


def _explicit_base_cue(front):
    match = re.search(r"<br>Cue:\s*([^<]+)", front, flags=re.I)
    return match.group(1).strip() if match else ""


def _normalized_cue_text(text):
    return re.sub(r"[^a-z0-9']+", " ", _strip_html(text).lower()).strip()


def _mask_answer_terms(text, answer):
    masked = text
    variants = [answer]
    variants.extend(
        word
        for word in re.findall(r"[A-Za-z']+", answer)
        if word.lower() not in FUNCTION_WORDS
    )
    for variant in sorted(set(variants), key=len, reverse=True):
        if len(variant) < 2:
            continue
        masked = re.sub(rf"\b{re.escape(variant)}\b", "_____", masked, flags=re.I)
    masked = re.sub(r"\buse\s+_____\s+for\s+", "", masked, flags=re.I)
    masked = re.sub(r"\b_____\s+(?:is|are|was|were)\s+used\s+for\s+", "used for ", masked, flags=re.I)
    masked = re.sub(r"\bwith\s+_____\s+as\s+", "with ", masked, flags=re.I)
    masked = re.sub(r"\s+", " ", masked).strip(" .;:")
    return masked


def _function_cue(topic, formula, reason, answer):
    reason_text = _mask_answer_terms(_strip_html(reason), answer)
    if reason_text and "_____" not in reason_text and 8 <= len(reason_text) <= 120:
        return reason_text
    formula_text = _mask_answer_terms(_strip_html(formula), answer)
    if formula_text and "_____" not in formula_text and len(formula_text) <= 80:
        return formula_text
    return topic.strip()


def _grammar_cues(original_front, prompt, answer, topic, formula, reason):
    cues = [("Function", _function_cue(topic, formula, reason, answer))]
    base = _explicit_base_cue(original_front) or _lexical_cue_from_chunk(answer)
    if base and _normalized_cue_text(base) == _normalized_cue_text(answer):
        base = EXACT_ANSWER_BASE_CUES.get(_normalized_cue_text(answer), "")
    if base:
        cues.append(("Base", base))
    return cues


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


GRAMMAR_TOPIC_FORMULAS = {
    "present perfect vs past simple": (
        "Decision rule<br>Ask whether the time is connected to now or finished.<br><br>"
        "Pattern<br>connected to now: have/has + past participle<br>finished past time: past simple<br><br>"
        "Common trap<br>Words like since, ever, and this week often keep the time connected to now."
    ),
    "present perfect continuous": (
        "Decision rule<br>Use present perfect continuous for an activity that started before now and is still relevant, especially with duration.<br><br>"
        "Pattern<br>have/has been + -ing<br><br>"
        "Common trap<br>Use present perfect simple when the result/count matters more than the ongoing activity."
    ),
    "past perfect": (
        "Decision rule<br>Use past perfect for the earlier of two past events.<br><br>"
        "Pattern<br>had + past participle<br><br>"
        "Common trap<br>If the events are simply told in order, past simple is usually enough."
    ),
    "future forms": (
        "Decision rule<br>Choose the future form from the evidence: plan, present evidence, schedule, or opinion.<br><br>"
        "Pattern<br>plan: be going to<br>present evidence: be going to<br>schedule: present simple<br>opinion/prediction: will"
    ),
    "narrative tenses": (
        "Decision rule<br>Use past continuous for background in progress, past simple for the main event, and past perfect for earlier background.<br><br>"
        "Pattern<br>background: was/were + -ing<br>event: past simple<br>earlier past: had + past participle"
    ),
    "conditionals": (
        "Decision rule<br>Match the condition form to reality and time.<br><br>"
        "Pattern<br>real future: if + present, will + base<br>unreal now/future: if + past, would + base<br>unreal past: if + had + V3, would have + V3"
    ),
    "mixed conditionals": (
        "Decision rule<br>Use mixed conditional when the if-clause time and result time are different.<br><br>"
        "Pattern<br>past condition -> present result: if + had + V3, would + base<br>present condition -> past result: if + past, would have + V3"
    ),
    "passive voice": (
        "Decision rule<br>Use passive when the receiver/result is more important than the doer, or the doer is unknown.<br><br>"
        "Pattern<br>be + past participle<br><br>"
        "Common trap<br>The tense is carried by be; the main action stays as a past participle."
    ),
    "relative clauses": (
        "Decision rule<br>Choose the relative word from the noun role: person, thing, possession, place, or whole clause.<br><br>"
        "Pattern<br>person: who/that<br>thing: which/that<br>possession: whose<br>place: where"
    ),
    "reported speech": (
        "Decision rule<br>Reported speech often shifts tense back and changes word order to statement order.<br><br>"
        "Pattern<br>question report: ask/wonder + if/whether/wh-word + subject + verb<br><br>"
        "Common trap<br>Do not keep direct-question inversion inside the reported clause."
    ),
    "noun clauses": (
        "Decision rule<br>A noun clause acts like a noun: subject, object, or complement of the sentence.<br><br>"
        "Pattern<br>wh-word/if/whether + subject + verb<br><br>"
        "Common trap<br>Use statement word order, not question word order."
    ),
    "gerund vs infinitive": (
        "Decision rule<br>The first verb controls whether the next verb is -ing or to + base verb.<br><br>"
        "Pattern<br>enjoy/avoid/admit + -ing<br>decide/plan/want + to + base verb<br><br>"
        "Common trap<br>remember + -ing means remembering a past action; remember + to means remembering to do a future duty."
    ),
    "used to patterns": (
        "Decision rule<br>used to means past habit; be used to means accustomed; get used to means become accustomed.<br><br>"
        "Pattern<br>used to + base verb<br>be/get used to + noun or -ing<br><br>"
        "Common trap<br>Do not put a base verb after be/get used to."
    ),
    "modal verbs": (
        "Decision rule<br>Choose the modal from function: ability, permission, possibility, advice, obligation, or prohibition.<br><br>"
        "Pattern<br>modal + base verb<br><br>"
        "Common trap<br>mustn't means not allowed; it does not mean don't have to."
    ),
    "modal perfect": (
        "Decision rule<br>Use modal + have + past participle to judge, infer, or imagine a past action.<br><br>"
        "Pattern<br>should have + V3 = missed advice<br>might have + V3 = past possibility<br>could have + V3 = unrealized possibility"
    ),
    "causatives": (
        "Decision rule<br>Use have/get + object + past participle when someone arranges for another person or process to do the action.<br><br>"
        "Pattern<br>have/get + object + past participle<br><br>"
        "Meaning<br>She got her team trained = she arranged/caused the training; she did not necessarily train them herself.<br><br>"
        "Common trap<br>Use a direct active verb only when the subject personally does the action."
    ),
    "articles": (
        "Decision rule<br>Choose the article from specificity, countability, and pronunciation.<br><br>"
        "Pattern<br>a/an = one nonspecific countable noun<br>the = specific or context-known<br>zero article = general plural/uncountable/abstract meaning"
    ),
    "prepositions": (
        "Decision rule<br>Many adjective/verb/noun + preposition pairs are fixed collocations; learn them as chunks.<br><br>"
        "Pattern<br>depend on, responsible for, comparable to<br><br>"
        "Common trap<br>Translate the whole chunk, not the preposition alone."
    ),
    "countable and uncountable nouns": (
        "Decision rule<br>Check whether the noun is counted as separate units or treated as a mass/abstract idea.<br><br>"
        "Pattern<br>countable plural: many/fewer + plural noun<br>uncountable: much/less + singular mass noun"
    ),
    "comparatives": (
        "Decision rule<br>Use comparative forms for two-item comparison and superlative forms for extremes in a group.<br><br>"
        "Pattern<br>comparative + than<br>the + superlative<br>the + comparative, the + comparative"
    ),
    "emphasis and inversion": (
        "Decision rule<br>Use inversion after fronted negative/restrictive expressions and clefting to emphasize one element.<br><br>"
        "Pattern<br>Only/Never/Rarely + auxiliary + subject + verb<br>It was + focus + that + clause"
    ),
    "sentence connectors": (
        "Decision rule<br>Choose the connector by logical relationship: cause, result, contrast, addition, or concession.<br><br>"
        "Pattern<br>because + reason<br>therefore + result<br>however + contrast"
    ),
    "participle clauses": (
        "Decision rule<br>Use participle clauses to compress extra information when the subject relationship is clear.<br><br>"
        "Pattern<br>active/same-time: -ing<br>completed earlier: having + V3<br>passive/result: V3"
    ),
    "reduced relative clauses": (
        "Decision rule<br>Reduce a relative clause only when the noun's role is clear.<br><br>"
        "Pattern<br>active: noun + -ing phrase<br>passive: noun + V3 phrase<br><br>"
        "Common trap<br>Keep the full relative clause if the reduced form sounds ambiguous or awkward."
    ),
    "hedging": (
        "Decision rule<br>Use hedging when evidence is limited or you want a cautious professional claim.<br><br>"
        "Pattern<br>may/could/seem/appear/possibly + claim<br><br>"
        "Common trap<br>Do not overstate a conclusion stronger than the evidence supports."
    ),
    "formal register": (
        "Decision rule<br>Formal register often prefers precise verbs, full clauses, and inverted conditionals in written contexts.<br><br>"
        "Pattern<br>ensure that + clause<br>carry out/conduct + noun<br>Should + subject + verb = if this happens"
    ),
    "advanced inversion": (
        "Decision rule<br>Fronted negative or restrictive phrases trigger auxiliary-subject inversion.<br><br>"
        "Pattern<br>Rarely/Never/Under no circumstances + auxiliary + subject + verb<br><br>"
        "Common trap<br>The inversion belongs in the first clause after the fronted phrase."
    ),
    "subjunctive and mandative structures": (
        "Decision rule<br>After formal demand/recommend/require structures, use the base verb in the that-clause.<br><br>"
        "Pattern<br>require/suggest/insist that + subject + base verb<br>It is essential that + subject + base verb"
    ),
    "clefting and fronting": (
        "Decision rule<br>Use clefting/fronting when you want to move focus to one specific element.<br><br>"
        "Pattern<br>What + clause + be + focus<br>It + be + focus + that + clause<br>The fact that + clause + be + focus"
    ),
    "ellipsis and substitution": (
        "Decision rule<br>Use substitution to avoid repeating a verb phrase or noun phrase when the meaning is already clear.<br><br>"
        "Pattern<br>do so = repeat the action<br>one/ones = repeat the noun"
    ),
    "advanced concession": (
        "Decision rule<br>Use concession structures to show the main idea remains true despite a difficulty or contrast.<br><br>"
        "Pattern<br>although + clause<br>adjective + though + clause<br>no matter + wh-word + clause"
    ),
    "nominalisation": (
        "Decision rule<br>Use nominalisation to turn actions or clauses into noun phrases for denser formal style.<br><br>"
        "Pattern<br>verb -> noun<br>the + noun + to-infinitive<br>due to + noun phrase"
    ),
    "parallelism": (
        "Decision rule<br>Items in a list or paired structure should have the same grammar shape.<br><br>"
        "Pattern<br>to plan, build, and maintain<br>planning, building, and maintaining<br><br>"
        "Common trap<br>Do not mix a noun, gerund, and full clause in one list unless there is a reason."
    ),
}


def _teaching_formula(topic, formula):
    teaching = GRAMMAR_TOPIC_FORMULAS.get(topic.lower())
    if not teaching:
        return formula
    if formula and formula not in teaching:
        return f"{teaching}<br><br>Card pattern<br>{html.escape(formula)}"
    return teaching


def _teaching_back(topic, reason, answer):
    teaching = GRAMMAR_TOPIC_FORMULAS.get(topic.lower())
    if not teaching:
        return reason
    instruction = "Use the decision rule in the Formula section, then explain why this sentence matches it."
    if "Full sentence:" in reason:
        before, full_sentence = reason.split("Full sentence:", 1)
        before = re.sub(r"(?:<br>\s*)+$", "", before.strip())
        parts = [before.strip(), instruction, f"Full sentence: {full_sentence.strip()}"]
        return "<br><br>".join(part for part in parts if part)
    parts = [reason]
    parts.append(instruction)
    if answer:
        parts.append(f"Full sentence: {html.escape(answer)}")
    return "<br><br>".join(part for part in parts if part)


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
                    _teaching_back(topic, reason, ""),
                    _teaching_formula(topic, formula),
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
            prompt = (
                _front_instruction("Type the correct/natural English form")
                + "<br>"
                + _front_cue_lines(_grammar_cues(front, prompt_base, answer_for_card, topic, formula, reason))
                + "<br><br>"
                + _front_without_choices(front)
            )
            prompt_mode = "type_exact" if len(answer_for_card.split()) <= 5 else "type_compare"
            if answer_for_card != answer:
                reason = f"{reason}<br><br>Full sentence: {html.escape(answer)}"
            answer = answer_for_card
        display_back = _teaching_back(topic, reason, "" if "Full sentence:" in reason else _extract_answer(item["back"]))
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
                display_back,
                _teaching_formula(topic, formula),
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
                and row["eng_id"] not in REJECT_AUDIO_SENTENCE_IDS
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
            if (
                lang != "eng"
                or sent_id not in audio
                or sent_id in INACCESSIBLE_AUDIO_SENTENCE_IDS
                or sent_id in REJECT_AUDIO_SENTENCE_IDS
                or not _is_clean_english_sentence(text)
            ):
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
                and sent_id not in REJECT_AUDIO_SENTENCE_IDS
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


def _valid_sentence_mining_row(row):
    sent_id = str(row.get("eng_id", ""))
    if sent_id in REJECT_SENTENCE_MINING_IDS:
        return False
    target = row.get("target", "")
    text = row.get("text", "")
    if target == "is used to":
        match = re.search(r"\bis used to\s+([A-Za-z']+)", text, flags=re.I)
        if match and not match.group(1).lower().endswith("ing"):
            return False
    return True


def _load_sentence_mining_sentences():
    """Mine Tatoeba English sentences for grammar pattern cloze cards."""
    cache_path = TATOEBA_DIR / "selected_eng_mining_sentences.tsv"
    reserved_audio_ids = {row["eng_id"] for row in _load_english_audio_sentences()}
    if cache_path.exists():
        with cache_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        rows = [row for row in rows if _valid_sentence_mining_row(row)]
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
                candidate = {
                    "eng_id": sent_id,
                    "text": text,
                    "target": target,
                    "level": level,
                    "audio_id": audio.get(sent_id, ""),
                    "has_audio": sent_id in audio and sent_id not in INACCESSIBLE_AUDIO_SENTENCE_IDS,
                }
                if pattern.search(text) and _valid_sentence_mining_row(candidate):
                    has_audio = sent_id in audio and sent_id not in INACCESSIBLE_AUDIO_SENTENCE_IDS
                    candidate["has_audio"] = has_audio
                    selected.append(candidate)
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
                _sentence_mining_back(target, text),
                _sentence_mining_formula(target, text),
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


INTERLEAVED_FORMULAS = {
    "present perfect vs past simple": (
        "Decision rule<br>"
        "Use present perfect when the time connects to now; use past simple when the time is finished.<br><br>"
        "Pattern<br>"
        "unfinished time: have/has + past participle<br>"
        "finished time: past simple<br><br>"
        "Signal words<br>"
        "since/for/ever/already often point to present perfect; exact finished times like in 2018/yesterday point to past simple."
    ),
    "present perfect vs past simple (experience)": (
        "Decision rule<br>"
        "Use present perfect for life experience without a finished time; use past simple for a specific past event.<br><br>"
        "Pattern<br>"
        "experience: have/has + past participle<br>"
        "specific past time: did + base verb or past simple<br><br>"
        "Common trap<br>"
        "ever asks whether the experience exists at any time in life, not when it happened."
    ),
    "past perfect vs past simple": (
        "Decision rule<br>"
        "Use past perfect when one past action was already complete before another past time/action.<br>"
        "Use past simple when events are told as a sequence in the past.<br><br>"
        "Pattern<br>"
        "earlier past event: had + past participle<br>"
        "story sequence: past simple<br><br>"
        "Signal words<br>"
        "by the time, already, and before often point to the earlier completed event."
    ),
    "present perfect continuous vs present perfect": (
        "Decision rule<br>"
        "Use present perfect continuous for an ongoing activity with duration; use present perfect for a completed result/count.<br><br>"
        "Pattern<br>"
        "ongoing duration: have/has been + -ing<br>"
        "completed result/count: have/has + past participle<br><br>"
        "Common trap<br>"
        "for two hours focuses on activity duration; three emails focuses on completed output."
    ),
    "will vs be going to": (
        "Decision rule<br>"
        "Use be going to for predictions based on present evidence; use will for opinion, belief, or spontaneous prediction.<br><br>"
        "Pattern<br>"
        "present evidence: am/is/are going to + base verb<br>"
        "opinion prediction: will + base verb"
    ),
    "second vs third conditional": (
        "Decision rule<br>"
        "Look at the result clause.<br>"
        "would + base verb means unreal now/future, so use past simple in the if-clause.<br>"
        "would have + past participle means unreal past, so use past perfect in the if-clause.<br><br>"
        "Pattern<br>"
        "second conditional: if + past simple, would + base verb<br>"
        "third conditional: if + had + past participle, would have + past participle<br><br>"
        "Common trap<br>"
        "had had is normal in third conditional: the first had is the auxiliary, the second had means possessed."
    ),
    "first vs second conditional": (
        "Decision rule<br>"
        "Use first conditional for a real future possibility; use second conditional for a hypothetical or less real situation.<br><br>"
        "Pattern<br>"
        "real future: if + present simple, will + base verb<br>"
        "hypothetical: if + past simple, would + base verb<br><br>"
        "Common trap<br>"
        "The past form in second conditional does not mean past time; it marks distance/unreality."
    ),
    "passive vs active": (
        "Decision rule<br>"
        "Use passive when the receiver of the action is the focus; use active when the doer is the focus.<br><br>"
        "Pattern<br>"
        "passive: be + past participle, optionally by + doer<br>"
        "active: subject/doer + verb + object"
    ),
    "used to vs be used to": (
        "Decision rule<br>"
        "used to describes a past habit that is no longer true; be used to means accustomed to something.<br><br>"
        "Pattern<br>"
        "past habit: used to + base verb<br>"
        "accustomed: am/is/are used to + noun or -ing"
    ),
    "used to vs get used to": (
        "Decision rule<br>"
        "used to describes an old habit; get used to describes the process of becoming accustomed.<br><br>"
        "Pattern<br>"
        "past habit: used to + base verb<br>"
        "becoming accustomed: get/getting/got used to + noun or -ing"
    ),
    "had better vs would rather": (
        "Decision rule<br>"
        "had better gives strong advice/warning; would rather states preference.<br><br>"
        "Pattern<br>"
        "strong advice: had better + base verb<br>"
        "preference: would rather + base verb"
    ),
    "despite vs in spite of": (
        "Decision rule<br>"
        "Both mean although something is true. Choose despite without of; choose in spite with of.<br><br>"
        "Pattern<br>"
        "despite + noun/-ing<br>"
        "in spite of + noun/-ing"
    ),
    "unless vs if not": (
        "Decision rule<br>"
        "unless means if not. Use unless for a compact negative condition; use if not when the negative condition is explicit.<br><br>"
        "Pattern<br>"
        "unless + positive clause<br>"
        "if + subject + do/does/did not + verb"
    ),
    "so that vs in order to": (
        "Decision rule<br>"
        "Use so that before a full clause with subject + verb; use in order to before an infinitive purpose phrase.<br><br>"
        "Pattern<br>"
        "so that + subject + modal/verb<br>"
        "in order to + base verb"
    ),
    "nevertheless vs however": (
        "Decision rule<br>"
        "Both show contrast. nevertheless is stronger and means despite that; however is a general contrast marker.<br><br>"
        "Punctuation<br>"
        "Both can start a new sentence. After a semicolon, nevertheless/however link two closely related clauses."
    ),
    "furthermore vs moreover": (
        "Decision rule<br>"
        "Both add information. furthermore adds another supporting point; moreover often adds a stronger or more decisive point.<br><br>"
        "Use<br>"
        "Choose based on the force of the second point, not grammar form."
    ),
    "not only inversion vs standard": (
        "Decision rule<br>"
        "When not only begins the clause, use auxiliary-subject inversion. In normal mid-sentence position, keep standard word order.<br><br>"
        "Pattern<br>"
        "fronted: Not only + auxiliary + subject + verb<br>"
        "standard: subject + not only + verb"
    ),
    "it-cleft vs standard": (
        "Decision rule<br>"
        "Use an it-cleft to emphasize one focused element; use standard order when no special focus structure is needed.<br><br>"
        "Pattern<br>"
        "emphasis: It was/is + focus + that + clause<br>"
        "standard: subject + verb + object/complement"
    ),
    "subjunctive vs indicative (mandative)": (
        "Decision rule<br>"
        "After formal verbs like require/insist/recommend that, use the base form for mandative subjunctive. Indicative uses the normal present form.<br><br>"
        "Pattern<br>"
        "formal requirement: require that + subject + base verb<br>"
        "ordinary statement: subject + present verb"
    ),
    "parallelism vs broken parallelism": (
        "Decision rule<br>"
        "Items in a list should share the same grammar shape. Match the missing item to the earlier items.<br><br>"
        "Pattern<br>"
        "to plan, build, and maintain = base verbs<br>"
        "planning, building, and maintaining = gerunds"
    ),
}


SENTENCE_MINING_FORMULAS = {
    "have been": (
        "Decision rule<br>Use have been when a plural/I/you/we/they subject has a state or activity connected from the past to now.<br><br>"
        "Pattern<br>subject + have been + complement/-ing/V3<br><br>"
        "Common trap<br>Use has been with he/she/it or a singular subject."
    ),
    "has been": (
        "Decision rule<br>Use has been when a singular subject has a state or activity connected from the past to now.<br><br>"
        "Pattern<br>singular subject + has been + complement/-ing/V3<br><br>"
        "Common trap<br>The time usually still matters now."
    ),
    "had": (
        "Decision rule<br>Use had as the past form of have for possession, experience, or obligation-like chunks.<br><br>"
        "Pattern<br>subject + had + object/complement"
    ),
    "would have": (
        "Decision rule<br>Use would have + past participle for an unreal past result: something did not happen, but it would have happened under different conditions.<br><br>"
        "Pattern<br>would have + past participle"
    ),
    "should have": (
        "Decision rule<br>Use should have + past participle for past advice, criticism, or expected action that did not happen.<br><br>"
        "Pattern<br>should have + past participle"
    ),
    "could have": (
        "Decision rule<br>Use could have + past participle for unrealized past ability or possibility.<br><br>"
        "Pattern<br>could have + past participle"
    ),
    "might have": (
        "Decision rule<br>Use might have + past participle for uncertain past possibility.<br><br>"
        "Pattern<br>might have + past participle"
    ),
    "used to": (
        "Decision rule<br>Use used to for a past habit or state that is no longer true.<br><br>"
        "Pattern<br>used to + base verb<br><br>"
        "Common trap<br>Do not confuse it with be used to + noun/-ing, which means accustomed."
    ),
    "will have": (
        "Decision rule<br>Use will have + past participle for an action completed before a future reference point.<br><br>"
        "Pattern<br>will have + past participle"
    ),
    "if I were": (
        "Decision rule<br>Use if I were for a hypothetical present/future condition, especially formal or careful English.<br><br>"
        "Pattern<br>if + subject + were, would/could + base verb"
    ),
    "I would have": (
        "Decision rule<br>Use would have + past participle for an unreal past result.<br><br>"
        "Pattern<br>subject + would have + past participle<br><br>"
        "Common trap<br>The condition may be implied, not always written in the same sentence."
    ),
    "was being": (
        "Decision rule<br>"
        "was/were being + past participle is past continuous passive.<br>"
        "Use it when the subject receives an action that was in progress at a past moment.<br><br>"
        "Pattern<br>"
        "receiver + was/were being + past participle<br><br>"
        "Common trap<br>"
        "being marks continuous passive, not a standalone meaning."
    ),
    "were being": (
        "Decision rule<br>"
        "was/were being + past participle is past continuous passive.<br>"
        "Use it when the subject receives an action that was in progress at a past moment.<br><br>"
        "Pattern<br>"
        "receiver + was/were being + past participle"
    ),
    "has been being": (
        "Decision rule<br>Use has been being + past participle for rare perfect continuous passive: an action has been in progress and the subject receives it.<br><br>"
        "Pattern<br>singular receiver + has been being + past participle<br><br>"
        "Common trap<br>This form is grammatical but uncommon; simpler passive forms are often more natural."
    ),
    "is used to": (
        "Decision rule<br>Use is used to when someone/something is accustomed to a noun or -ing action.<br><br>"
        "Pattern<br>is used to + noun/-ing<br><br>"
        "Common trap<br>is used to + base verb usually means utilized in order to, not accustomed."
    ),
    "get used to": (
        "Decision rule<br>Use get used to for the process of becoming accustomed.<br><br>"
        "Pattern<br>get/getting/got used to + noun/-ing"
    ),
    "had better": (
        "Decision rule<br>Use had better for strong advice, often with an implied warning or bad consequence.<br><br>"
        "Pattern<br>had better + base verb"
    ),
    "would rather": (
        "Decision rule<br>Use would rather to express preference.<br><br>"
        "Pattern<br>would rather + base verb"
    ),
    "in spite of": (
        "Decision rule<br>Use in spite of to introduce a concession before a noun phrase or -ing phrase.<br><br>"
        "Pattern<br>in spite of + noun/-ing"
    ),
    "despite": (
        "Decision rule<br>Use despite to introduce a concession before a noun phrase or -ing phrase.<br><br>"
        "Pattern<br>despite + noun/-ing<br><br>"
        "Common trap<br>Do not write despite of."
    ),
    "rather than": (
        "Decision rule<br>Use rather than to choose one option instead of another.<br><br>"
        "Pattern<br>preferred option + rather than + rejected option"
    ),
    "by the time": (
        "Decision rule<br>Use by the time to mark the deadline/reference point before which another action is complete.<br><br>"
        "Pattern<br>by the time + clause, earlier/completed event"
    ),
    "so that": (
        "Decision rule<br>Use so that to introduce a purpose/result clause with its own subject and verb.<br><br>"
        "Pattern<br>so that + subject + modal/verb"
    ),
    "in case": (
        "Decision rule<br>Use in case for precaution: do something now because something might happen later.<br><br>"
        "Pattern<br>action + in case + possible situation"
    ),
    "unless": (
        "Decision rule<br>Use unless to mean if not.<br><br>"
        "Pattern<br>unless + positive clause<br><br>"
        "Common trap<br>Do not add another not unless you really need a double negative meaning."
    ),
    "provided that": (
        "Decision rule<br>Use provided that for a condition meaning only if.<br><br>"
        "Pattern<br>main clause + provided that + condition"
    ),
    "as long as": (
        "Decision rule<br>Use as long as for a condition meaning only if / provided that.<br><br>"
        "Pattern<br>main clause + as long as + condition"
    ),
    "even if": (
        "Decision rule<br>Use even if for a hypothetical condition that does not change the main result.<br><br>"
        "Pattern<br>even if + condition, main clause still true"
    ),
    "no matter": (
        "Decision rule<br>Use no matter to say the result is unchanged across all possibilities.<br><br>"
        "Pattern<br>no matter + wh-word + clause"
    ),
    "nevertheless": (
        "Decision rule<br>Use nevertheless to introduce a strong contrast meaning despite that.<br><br>"
        "Pattern<br>previous idea; nevertheless, contrasting result"
    ),
    "moreover": (
        "Decision rule<br>Use moreover to add a further, often stronger, supporting point.<br><br>"
        "Pattern<br>sentence. Moreover, additional point."
    ),
    "furthermore": (
        "Decision rule<br>Use furthermore to add another supporting point.<br><br>"
        "Pattern<br>sentence. Furthermore, additional point."
    ),
    "consequently": (
        "Decision rule<br>Use consequently to introduce a result caused by the previous idea.<br><br>"
        "Pattern<br>cause/context; consequently, result"
    ),
    "meanwhile": (
        "Decision rule<br>Use meanwhile for something happening at the same time, often in another place or thread of events.<br><br>"
        "Pattern<br>event A. Meanwhile, event B."
    ),
    "indeed": (
        "Decision rule<br>Use indeed to emphasize or confirm that a statement is true.<br><br>"
        "Pattern<br>indeed + emphasized/confirming statement"
    ),
    "obviously": (
        "Decision rule<br>Use obviously when the speaker presents something as clear or easy to see.<br><br>"
        "Pattern<br>obviously + statement"
    ),
    "fortunately": (
        "Decision rule<br>Use fortunately to frame the whole statement as a lucky/good outcome.<br><br>"
        "Pattern<br>fortunately, positive outcome"
    ),
    "unfortunately": (
        "Decision rule<br>Use unfortunately to frame the whole statement as a bad or unlucky outcome.<br><br>"
        "Pattern<br>unfortunately, negative outcome"
    ),
    "not only": (
        "Decision rule<br>Use not only to introduce the first part of an emphatic addition.<br><br>"
        "Pattern<br>not only ... but also ...<br><br>"
        "Common trap<br>If not only starts the clause, use auxiliary-subject inversion."
    ),
    "it is": (
        "Decision rule<br>Use it is/was + focus + that to emphasize one part of the sentence.<br><br>"
        "Pattern<br>it is/was + focus + that + clause"
    ),
    "what is": (
        "Decision rule<br>Use what-clefting to put the focused information after be.<br><br>"
        "Pattern<br>what + clause + is/was + focus"
    ),
    "the fact that": (
        "Decision rule<br>Use the fact that to turn a whole clause into a noun phrase.<br><br>"
        "Pattern<br>the fact that + subject + verb"
    ),
    "regardless of": (
        "Decision rule<br>Use regardless of to mean not affected by something.<br><br>"
        "Pattern<br>regardless of + noun/-ing"
    ),
    "owing to": (
        "Decision rule<br>Use owing to for a formal cause/reason phrase.<br><br>"
        "Pattern<br>owing to + noun phrase"
    ),
    "apart from": (
        "Decision rule<br>Use apart from for exception or addition, depending on context.<br><br>"
        "Pattern<br>apart from + noun/-ing"
    ),
    "in light of": (
        "Decision rule<br>Use in light of to introduce context/evidence that affects a decision or interpretation.<br><br>"
        "Pattern<br>in light of + noun phrase"
    ),
}


def _conditional_if_i_had_formula(text):
    lowered = text.lower()
    if "would have" in lowered or "could have" in lowered or "should have" in lowered or "might have" in lowered:
        return (
            "Decision rule<br>"
            "The result clause has would/could/should/might have + past participle, so this is an unreal past condition.<br><br>"
            "Pattern<br>"
            "if + had + past participle, would/could/should/might have + past participle<br><br>"
            "Common trap<br>"
            "If the main verb is have, the if-clause becomes had had: auxiliary had + main verb had."
        )
    return (
        "Decision rule<br>"
        "The result clause has would/could + base verb, so this is an unreal present/future condition.<br><br>"
        "Pattern<br>"
        "if + past simple, would/could + base verb<br><br>"
        "Common trap<br>"
        "The past form marks unreality here; it does not mean past time."
    )


def _sentence_mining_formula(target, text):
    if target == "if I had":
        return _conditional_if_i_had_formula(text)
    return SENTENCE_MINING_FORMULAS.get(
        target,
        "Decision rule<br>Use the target chunk because the sentence context matches its grammar function.<br><br>"
        f"Target function<br>{html.escape(_target_cue(target))}",
    )


def _sentence_mining_back(target, text):
    if target == "if I had":
        return (
            f"Full sentence: {html.escape(text)}<br><br>"
            "Check the result clause first, then choose the if-clause pattern."
        )
    if target in {"was being", "were being"}:
        return (
            f"Full sentence: {html.escape(text)}<br><br>"
            "The subject receives the action, and the action was in progress at that past moment."
        )
    return "Type the missing chunk from the real sentence."


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
                INTERLEAVED_FORMULAS.get(
                    topic_name,
                    f"Decision rule<br>Choose the form whose grammar function matches the sentence context.<br><br>Contrast<br>{html.escape(topic_name)}",
                ),
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
