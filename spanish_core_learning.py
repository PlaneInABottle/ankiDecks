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


def _front_cue(label, text):
    return f'<span class="front-cue">{html.escape(label)}: {html.escape(text)}</span>'


def _typed_contrast_front(choose_front):
    prompt = re.sub(r"(?i)^choose:?\s*", "", choose_front).strip()
    options = re.findall(r"<br>[A-Z]\)\s*([^<]+)", prompt)
    prompt = re.sub(r"<br>[A-Z]\)\s*[^<]+", "", prompt).strip()
    prompt = prompt.replace("___", "_____")
    option_cue = ""
    if options:
        option_cue = f"<br><span class=\"front-cue\">Contrast: {' / '.join(html.escape(option.strip()) for option in options)}</span>"
    return f"{_front_instruction('Type the correct Spanish form')}<br>{prompt}{option_cue}"


def _plain_front_text(text):
    without_cues = re.sub(r'<span class="front-cue">.*?</span>', "", text or "", flags=re.DOTALL)
    plain = html.unescape(re.sub(r"<[^>]+>", " ", without_cues))
    plain = re.sub(
        r"^(Type the correct Spanish form|Complete the Spanish from context|Listen first, then complete the chunk)\s+",
        "",
        plain.strip(),
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", plain).strip()


SPANISH_TOPIC_FALLBACKS = {
    "noun gender": "Learn nouns with their article. Gender controls articles and adjective endings.",
    "plural nouns": "Choose plural endings from the final sound of the singular noun.",
    "adjective agreement": "Adjectives change to match the noun in gender and number.",
    "subject pronouns": "Choose pronouns by person, number, and formality.",
    "ser basics": "Use ser for identity, origin, profession, and stable classification.",
    "negation": "Put no before the conjugated verb.",
    "yes-no questions": "Spanish can keep statement word order; punctuation and intonation mark the question.",
    "ser vs estar": "Use ser for identity/category; use estar for location or temporary state.",
    "regular -ar present": "Remove -ar and add the present ending for the subject.",
    "regular -er and -ir present": "Remove -er/-ir and add the present ending for the subject.",
    "articles": "Choose article by definiteness, gender, and number.",
    "hay": "Use hay for there is / there are; it does not change for singular or plural.",
    "question words": "Choose the question word by the information requested.",
    "tener and tener que": "tener means have; tener que + infinitive means have to.",
    "ir a infinitive": "Use ir + a + infinitive for near future plans.",
    "possessive adjectives": "Choose possessive adjective by owner and by the noun owned.",
    "gustar basics": "The liked thing controls gusta/gustan; the person is marked by an indirect object pronoun.",
    "reflexive verbs": "Use a reflexive pronoun when the subject does the action to itself.",
    "direct object pronouns": "Use lo/la/los/las to replace the direct object.",
    "regular preterite": "Use preterite for completed past events.",
    "irregular preterite": "Use the irregular preterite stem and endings for completed past events.",
    "imperfect basics": "Use imperfect for background, description, habitual past, or ongoing past state.",
    "preterite vs imperfect": "Use preterite for completed events and imperfect for background/habit/state.",
    "comparatives": "Use más/menos ... que for more/less than; tan ... como for as ... as.",
    "informal commands": "Use tú command forms for direct informal instructions.",
    "por vs para": "Use por for cause/route/exchange; use para for purpose/deadline/recipient/destination.",
    "indirect object pronouns": "Use me/te/le/nos/les for the person affected or receiving.",
    "double object pronouns": "Put indirect object pronoun before direct object pronoun; le/les becomes se before lo/la/los/las.",
    "present progressive": "Use estar + gerund for actions happening right now.",
    "present perfect": "Use haber + past participle for experiences or past actions connected to now.",
    "relative clauses and connectors": "Use connectors to join ideas; choose the connector by relationship.",
    "location prepositions": "Use location prepositions to state where something is relative to something else.",
    "ordinal basics": "Ordinal words identify order in a sequence.",
    "muy vs mucho": "muy modifies adjectives/adverbs; mucho modifies verbs or nouns.",
    "todo and cada": "todo means all/every as a whole; cada means each individual item.",
    "obligation variants": "Use tener que/deber/hay que to express obligation with different tone or subject.",
    "quedar vs quedarse": "quedar often means remain/be located/fit; quedarse means stay or become in a state.",
    "emotion verbs with prepositions": "Learn emotion verbs with their required prepositions.",
    "numbers 0 to 20": "Use fixed number forms for counting and basic quantities.",
    "basic prepositions": "Use prepositions as fixed relation words; learn short chunks.",
    "basic word order": "Spanish basic word order is subject + verb + complement, but pronouns and emphasis can shift it.",
    "polite phrases": "Use fixed polite chunks for greetings, requests, and thanks.",
    "ir present": "Use irregular present forms of ir for movement and near future.",
    "tener present": "Use irregular present forms of tener for possession and age/obligation chunks.",
    "hacer present": "Use irregular present forms of hacer for doing/making and weather chunks.",
    "querer and poder present": "Use stem-changing forms for querer/poder in present tense.",
    "estar present": "Use estar forms for location, temporary state, and progressive tense.",
    "adverbs of frequency": "Place frequency adverbs where they naturally modify the verb phrase.",
    "adjective position basics": "Most descriptive adjectives follow the noun; some common/evaluative adjectives precede it.",
    "a plus el and de plus el": "Contract a + el to al and de + el to del.",
    "near future with ir": "Use ir + a + infinitive for plans and near future.",
    "basic subjunctive triggers": "Use subjunctive after triggers of desire, doubt, emotion, or influence.",
    "conditional basics": "Use conditional for would statements and polite/hypothetical results.",
    "aunque indicative vs subjunctive recognition": "Use indicative for known facts; subjunctive for uncertain or hypothetical concession.",
    "reported speech basics": "Shift tense and person as needed when reporting what someone said.",
}


SPANISH_INTERLEAVED_FORMULAS = {
    "ser vs estar (identity vs state)": (
        "Decision rule<br>Use ser for identity/profession/category; use estar for temporary state or condition.<br><br>"
        "Pattern<br>ser + identity noun/adjective<br>estar + state adjective"
    ),
    "ser vs estar (origin vs location)": (
        "Decision rule<br>Use ser de for origin; use estar en for current location.<br><br>"
        "Pattern<br>ser + de + origin<br>estar + en + location"
    ),
    "present vs present progressive": (
        "Decision rule<br>Use simple present for habits/general facts; use present progressive for right now.<br><br>"
        "Pattern<br>habit: present verb<br>right now: estar + gerund"
    ),
    "saber vs conocer": (
        "Decision rule<br>Use saber for facts/skills; use conocer for people, places, and familiarity.<br><br>"
        "Pattern<br>saber + fact/infinitive<br>conocer + a + person"
    ),
    "gustar singular vs plural": (
        "Decision rule<br>The liked thing controls gusta/gustan.<br><br>"
        "Pattern<br>singular liked thing: gusta<br>plural liked thing: gustan"
    ),
    "preterite vs imperfect (event vs background)": (
        "Decision rule<br>Use preterite for completed events; use imperfect for background or repeated past habits.<br><br>"
        "Pattern<br>event: preterite<br>background/habit: imperfect"
    ),
    "preterite vs imperfect (action vs state)": (
        "Decision rule<br>Use preterite for a completed action in sequence; use imperfect for an ongoing state/description.<br><br>"
        "Pattern<br>action/event: preterite<br>state/background: imperfect"
    ),
    "ser vs ir preterite (same forms)": (
        "Decision rule<br>Use context to decide meaning because fui/fue/etc. can mean went or was.<br><br>"
        "Pattern<br>movement + destination = ir<br>identity/event description = ser"
    ),
    "por vs para (reason vs purpose)": (
        "Decision rule<br>Use para for purpose/destination/recipient/deadline; use por for reason/cause/route/exchange.<br><br>"
        "Pattern<br>para + purpose/destination<br>por + reason/cause/path"
    ),
    "imperfect vs preterite (description vs event)": (
        "Decision rule<br>Use imperfect for scene-setting description; use preterite for the interrupting/completed event.<br><br>"
        "Pattern<br>background: imperfect<br>event: preterite"
    ),
    "ser vs estar (characteristic vs result)": (
        "Decision rule<br>Use ser for defining characteristics; use estar for current condition/result.<br><br>"
        "Pattern<br>ser + identity/definition<br>estar + temporary/current state"
    ),
    "indicative vs subjunctive (fact vs doubt)": (
        "Decision rule<br>Use indicative after belief/known fact; use subjunctive after doubt, denial, desire, or uncertainty.<br><br>"
        "Pattern<br>creo que + indicative<br>no creo que + subjunctive"
    ),
    "conditional vs imperfect (hypothetical vs past)": (
        "Decision rule<br>Use conditional for would/hypothetical result; use imperfect for repeated or ongoing past.<br><br>"
        "Pattern<br>hypothetical result: conditional<br>past habit/background: imperfect"
    ),
}


SENTENCE_TARGET_FORMULAS = {
    "hay": "Decision rule<br>Use hay for both there is and there are.<br><br>Pattern<br>hay + noun phrase",
    "ser": "Decision rule<br>Use ser for identity, origin, profession, and stable classification.<br><br>Pattern<br>subject + ser form + identity/category",
    "estar": "Decision rule<br>Use estar for location, temporary state, and progressive tense.<br><br>Pattern<br>subject + estar form + location/state",
    "tener": "Decision rule<br>Use tener for possession, age, and tener que obligation chunks.<br><br>Pattern<br>subject + tener form + noun / que + infinitive",
    "querer": "Decision rule<br>Use querer for wanting; present forms stem-change except nosotros.<br><br>Pattern<br>quiero/quieres/quiere/queremos/quieren + noun/infinitive",
    "poder": "Decision rule<br>Use poder for can/be able to; present forms stem-change except nosotros.<br><br>Pattern<br>puedo/puedes/puede/podemos/pueden + infinitive",
    "ir": "Decision rule<br>Use ir for going; use ir a + infinitive for near future.<br><br>Pattern<br>voy/vas/va/vamos/van + a + infinitive",
    "gustar": "Decision rule<br>The liked thing controls gusta/gustan; the person is an indirect object pronoun.<br><br>Pattern<br>me/te/le/nos/les + gusta/gustan + liked thing",
    "preterite": "Decision rule<br>Use preterite for completed past events.<br><br>Pattern<br>completed past action + preterite form",
    "imperfect": "Decision rule<br>Use imperfect for background, description, repeated past, or ongoing past state.<br><br>Pattern<br>background/habit/state + imperfect form",
    "por": "Decision rule<br>Use por for reason/cause, route, exchange, or duration.<br><br>Pattern<br>por + cause/path/exchange",
    "para": "Decision rule<br>Use para for purpose, destination, recipient, or deadline.<br><br>Pattern<br>para + purpose/destination/recipient",
    "present perfect": "Decision rule<br>Use haber + past participle for experiences or past actions connected to now.<br><br>Pattern<br>he/has/ha/hemos/han + past participle",
    "subjunctive trigger": "Decision rule<br>Use subjunctive after desire, doubt, emotion, influence, or uncertainty triggers.<br><br>Pattern<br>trigger + que + subjunctive",
}


def _topic_formula(topic):
    base = SPANISH_TOPIC_FALLBACKS.get(topic["topic"], topic.get("use", "Choose the form from meaning and sentence role."))
    formula = topic.get("formula", "")
    parts = [f"Decision rule<br>{html.escape(base)}"]
    if formula:
        parts.append(f"Pattern<br>{html.escape(formula)}")
    trap = topic.get("trap", "")
    if trap:
        parts.append(f"Common trap<br>{html.escape(trap)}")
    return "<br><br>".join(parts)


def _sentence_target_formula(target):
    if target in {"es", "soy", "eres", "son"}:
        return SENTENCE_TARGET_FORMULAS["ser"]
    if target in {"estoy", "estás", "está", "estamos", "están"}:
        return SENTENCE_TARGET_FORMULAS["estar"]
    if target in {"tengo", "tienes", "tiene", "tenemos", "tengo que", "tienes que"}:
        return SENTENCE_TARGET_FORMULAS["tener"]
    if target in {"quiero", "quieres", "quiere"}:
        return SENTENCE_TARGET_FORMULAS["querer"]
    if target in {"puedo", "puedes", "puede"}:
        return SENTENCE_TARGET_FORMULAS["poder"]
    if target in {"voy", "vas", "va", "vamos", "voy a", "vas a", "va a"}:
        return SENTENCE_TARGET_FORMULAS["ir"]
    if target in {"me gusta", "me gustan", "te gusta", "le gusta"}:
        return SENTENCE_TARGET_FORMULAS["gustar"]
    if target in {"fui", "fue", "tuve", "hice", "dije", "vi"}:
        return SENTENCE_TARGET_FORMULAS["preterite"]
    if target in {"era", "estaba", "tenía"}:
        return SENTENCE_TARGET_FORMULAS["imperfect"]
    if target in {"he", "has", "ha", "hemos"}:
        return SENTENCE_TARGET_FORMULAS["present perfect"]
    if target in {"quiero que", "espero que"}:
        return SENTENCE_TARGET_FORMULAS["subjunctive trigger"]
    if target in SENTENCE_TARGET_FORMULAS:
        return SENTENCE_TARGET_FORMULAS[target]
    return (
        f"Decision rule<br>Use {html.escape(target)} when the sentence context matches its meaning and grammar role.<br><br>"
        f"Pattern<br>{html.escape(target)}"
    )


def _derive_blank_answer(front, full_answer):
    prompt = _plain_front_text(front)
    if "->" in prompt:
        arrow_tail = prompt.rsplit("->", 1)[1].strip()
        if "_____" in arrow_tail:
            prompt = arrow_tail
    answer = re.sub(r"\s+", " ", full_answer or "").strip()
    if "_____" not in prompt or not answer:
        return answer
    before, after = prompt.split("_____", 1)
    before = before.strip().strip(" ,.;:¿?¡!")
    after = after.strip().strip(" ,.;:¿?¡!")
    candidate = answer.strip(" ,.;:¿?¡!")
    if before and candidate.lower().startswith(before.lower()):
        candidate = candidate[len(before):].strip()
    if after and candidate.lower().endswith(after.lower()):
        candidate = candidate[: -len(after)].strip()
    candidate = candidate.strip(" ,.;:¿?¡!")
    return candidate or answer


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
    teaching_formula = _topic_formula(topic)
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
            teaching_formula,
            examples,
        )
    ]
    choose_front, choose_answer, choose_reason = topic["choose"]
    typed_contrast_answer = _strip_choice_prefix(choose_answer)
    typed_contrast_front = _typed_contrast_front(choose_front)
    typed_answer = _derive_blank_answer(typed_contrast_front, typed_contrast_answer)
    typed_contrast_mode = "type_exact" if len(typed_answer.split()) <= 4 else "type_compare"
    cards.append(
        _card(
            f"{level}::{slug}::typed_contrast",
            level,
            topic_name,
            "typed_contrast",
            typed_contrast_mode,
            typed_contrast_front,
            typed_answer,
            f"{choose_reason}<br><br>Full sentence: {typed_contrast_answer}",
            teaching_formula,
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
            teaching_formula,
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
            teaching_formula,
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
                    f"{_front_instruction('Write any valid Spanish sentence or chunk using this pattern')}<br>"
                    f"<span class=\"topic-label\">{topic_name}</span><br>"
                    f"{topic['formula']}<br><br>"
                    f"{_front_instruction(f'Model answer {index}: compare grammar, word order, accents')}"
                ),
                example,
                topic["use"],
                teaching_formula,
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


def _audio_word_cloze_target(target):
    """Choose one word from a sentence-mining target for audio cloze practice."""
    words = target.split()
    if len(words) == 1:
        return target, re.compile(TARGET_PATTERNS[target])

    if words[0] in {"me", "te", "le"} and len(words) > 1:
        answer = words[1]
    else:
        answer = words[0]
    return answer, re.compile(rf"\b{re.escape(answer)}\b", re.IGNORECASE)


def _dictation_cards():
    """Audio word cloze cards using the old dictation SourceIDs for stable updates."""
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
        target = row["target"]
        answer, pattern = _audio_word_cloze_target(target)
        cloze = pattern.sub("_____", spa_text, count=1)
        if cloze == spa_text:
            continue
        sound = f"[sound:tatoeba_spa_{spa_id}.mp3]"
        source = f"Tatoeba spa:{spa_id} eng:{row['eng_id']}"
        attribution = TATOEBA_ATTRIBUTION.format(spa_id=spa_id, eng_id=row["eng_id"])
        cards.append(
            _card(
                f"tatoeba_dictation::{level}::{spa_id}::{row['eng_id']}",
                level,
                "listening word cloze",
                "audio_cloze",
                "type_exact",
                f"{sound}<br><br>{_front_instruction('Listen first, then type the missing word')}<br>{cloze}",
                answer,
                f"Listen first, type only the missing word, then replay and shadow the full sentence once.<br><br>Meaning: {eng_text}",
                _sentence_target_formula(target),
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
        is_invariable = "|" not in paradigm
        formula = "invariable" if is_invariable else "yo | tú | él/ella/usted | nosotros | vosotros | ellos/ellas/ustedes"
        type_note = "Type the invariable form" if is_invariable else "Type all 6 forms separated by |"
        cards.append(
            _card(
                f"verb_paradigm::{level}::{verb}::{tense}",
                level,
                f"verb conjugation: {verb}",
                "verb_paradigm",
                "type_compare",
                f"{_front_instruction('Conjugate')} <b>{verb}</b> – {tense} tense<br><span class=\"type-note\">{type_note}</span>",
                paradigm,
                f"{verb} ({tense}) = {meaning}",
                formula,
                "",
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


TARGETED_RECALL_CARDS = [
    ("a1_1_foundations", "ser vs estar targeted recall", "Soy _____ Turquía.", "de", "ser de = origin", "origin after ser", "- Soy de Turquía<br>- Ella es de México"),
    ("a1_1_foundations", "ser vs estar targeted recall", "Estoy _____ casa.", "en", "estar en = location", "location after estar", "- Estoy en casa<br>- Estamos en la oficina"),
    ("a1_1_foundations", "ser vs estar targeted recall", "Mi hermano _____ médico.", "es", "ser = identity/profession", "ser + profession", "- Mi hermano es médico<br>- Laura es profesora"),
    ("a1_1_foundations", "ser vs estar targeted recall", "La puerta _____ abierta ahora.", "está", "estar = current state/result", "estar + state", "- La puerta está abierta<br>- El café está frío"),
    ("a1_1_foundations", "ser vs estar targeted recall", "La reunión _____ a las tres.", "es", "ser = scheduled event time", "ser + time for events", "- La reunión es a las tres<br>- La clase es mañana"),
    ("a1_1_foundations", "ser vs estar targeted recall", "Hoy _____ lunes.", "es", "ser = date/day", "ser + day/date", "- Hoy es lunes<br>- Mañana es viernes"),
    ("a1_2_core_sentences", "direct object pronoun targeted recall", "Veo el libro. _____ veo.", "Lo", "lo replaces masculine singular direct object", "lo = it/him", "- Lo veo<br>- Lo necesito"),
    ("a1_2_core_sentences", "direct object pronoun targeted recall", "Veo la mesa. _____ veo.", "La", "la replaces feminine singular direct object", "la = it/her", "- La veo<br>- La necesito"),
    ("a1_2_core_sentences", "direct object pronoun targeted recall", "Compro los zapatos. _____ compro.", "Los", "los replaces masculine plural direct object", "los = them", "- Los compro<br>- Los llevo"),
    ("a1_2_core_sentences", "direct object pronoun targeted recall", "Compro las entradas. _____ compro.", "Las", "las replaces feminine plural direct object", "las = them", "- Las compro<br>- Las tengo"),
    ("a1_2_core_sentences", "indirect object pronoun targeted recall", "Doy el libro a Ana. _____ doy el libro.", "Le", "le = to him/her/you formal", "le + verb", "- Le doy el libro<br>- Le escribo mañana"),
    ("a1_2_core_sentences", "indirect object pronoun targeted recall", "Doy los libros a mis amigos. _____ doy los libros.", "Les", "les = to them/you plural", "les + verb", "- Les doy los libros<br>- Les escribo hoy"),
    ("a1_2_core_sentences", "gustar targeted recall", "Me _____ el café.", "gusta", "gustar agrees with the thing liked", "singular thing -> gusta", "- Me gusta el café<br>- Te gusta la música"),
    ("a1_2_core_sentences", "gustar targeted recall", "Me _____ las películas.", "gustan", "gustar agrees with the thing liked", "plural thing -> gustan", "- Me gustan las películas<br>- Nos gustan los libros"),
    ("a1_2_core_sentences", "gustar targeted recall", "A ella _____ gusta bailar.", "le", "le marks the person who likes something", "a ella -> le", "- A ella le gusta bailar<br>- A Juan le gusta correr"),
    ("a1_2_core_sentences", "gustar targeted recall", "A nosotros _____ gustan los perros.", "nos", "nos marks what we like", "a nosotros -> nos", "- A nosotros nos gustan los perros<br>- Nos gusta estudiar"),
    ("a1_2_core_sentences", "reflexive verb targeted recall", "Yo _____ levanto temprano.", "me", "me marks a reflexive action for yo", "yo -> me", "- Me levanto temprano<br>- Me ducho por la mañana"),
    ("a1_2_core_sentences", "reflexive verb targeted recall", "Tú _____ acuestas tarde.", "te", "te marks a reflexive action for tú", "tú -> te", "- Te acuestas tarde<br>- Te despiertas a las siete"),
    ("a1_2_core_sentences", "reflexive verb targeted recall", "Ella _____ viste rápido.", "se", "se marks a reflexive action for él/ella/usted", "ella -> se", "- Ella se viste rápido<br>- Él se lava las manos"),
    ("a1_2_core_sentences", "reflexive verb targeted recall", "Nosotros _____ quedamos en casa.", "nos", "nos marks a reflexive/reciprocal action for nosotros", "nosotros -> nos", "- Nos quedamos en casa<br>- Nos vemos mañana"),
    ("a2_1_daily_past", "preterite targeted recall", "Ayer yo _____ al mercado.", "fui", "preterite of ir for completed movement", "ayer + ir -> fui", "- Ayer fui al mercado<br>- Fui a la oficina"),
    ("a2_1_daily_past", "preterite targeted recall", "Anoche nosotros _____ tarde.", "llegamos", "preterite for completed action at a specific time", "anoche + llegar", "- Anoche llegamos tarde<br>- Llegamos a las ocho"),
    ("a2_1_daily_past", "preterite targeted recall", "La semana pasada ella _____ mucho.", "trabajó", "preterite for completed past period", "la semana pasada + trabajar", "- Ella trabajó mucho<br>- Trabajó en casa"),
    ("a2_1_daily_past", "preterite targeted recall", "Ayer ellos _____ una película.", "vieron", "preterite of ver for completed event", "ayer + ver", "- Ellos vieron una película<br>- Vieron el partido"),
    ("a2_1_daily_past", "imperfect targeted recall", "De niño, yo _____ mucho al fútbol.", "jugaba", "imperfect for repeated past habit", "de niño + jugar", "- De niño, jugaba al fútbol<br>- Jugaba cada tarde"),
    ("a2_1_daily_past", "imperfect targeted recall", "Antes nosotros _____ cerca del mar.", "vivíamos", "imperfect for past background/habit", "antes + vivir", "- Antes vivíamos cerca del mar<br>- Vivíamos en Ankara"),
    ("a2_1_daily_past", "imperfect targeted recall", "Cuando era joven, ella _____ mucho.", "leía", "imperfect for repeated past habit", "cuando era joven + leer", "- Ella leía mucho<br>- Leía cada noche"),
    ("a2_1_daily_past", "imperfect targeted recall", "La casa _____ muy tranquila.", "era", "imperfect of ser for description", "description in the past", "- La casa era tranquila<br>- El día era largo"),
    ("a2_1_daily_past", "preterite vs imperfect targeted recall", "Mientras yo estudiaba, mi hermano _____.", "llegó", "preterite interrupts imperfect background", "interruption event", "- Mientras estudiaba, llegó mi hermano<br>- Cuando dormía, sonó el teléfono"),
    ("a2_1_daily_past", "preterite vs imperfect targeted recall", "Yo _____ cuando sonó el teléfono.", "dormía", "imperfect gives the background action", "background action", "- Dormía cuando sonó el teléfono<br>- Comía cuando llegó Ana"),
    ("a2_1_daily_past", "preterite vs imperfect targeted recall", "Primero cerré la puerta y después _____ la luz.", "apagué", "preterite for sequence of completed actions", "action sequence", "- Cerré la puerta y apagué la luz<br>- Llegué y llamé"),
    ("a2_1_daily_past", "preterite vs imperfect targeted recall", "Todos los veranos nosotros _____ a la playa.", "íbamos", "imperfect for repeated past routine", "past routine", "- Íbamos a la playa<br>- Visitábamos a mis abuelos"),
    ("a2_2_natural_spanish", "por vs para targeted recall", "Trabajo _____ ganar dinero.", "para", "para + infinitive = purpose", "purpose", "- Trabajo para ganar dinero<br>- Estudio para aprender"),
    ("a2_2_natural_spanish", "por vs para targeted recall", "Gracias _____ tu ayuda.", "por", "por = reason/cause", "reason", "- Gracias por tu ayuda<br>- Lo hice por ti"),
    ("a2_2_natural_spanish", "por vs para targeted recall", "Este regalo es _____ Ana.", "para", "para = recipient/destination", "recipient", "- Es para Ana<br>- La carta es para ti"),
    ("a2_2_natural_spanish", "por vs para targeted recall", "Caminamos _____ el parque.", "por", "por = through/around a place", "movement through", "- Caminamos por el parque<br>- Pasé por tu casa"),
    ("a2_2_natural_spanish", "por vs para targeted recall", "Lo necesito _____ mañana.", "para", "para = deadline", "deadline", "- Lo necesito para mañana<br>- Es para el viernes"),
    ("a2_2_natural_spanish", "por vs para targeted recall", "No salí _____ la lluvia.", "por", "por = cause", "cause", "- No salí por la lluvia<br>- Llegué tarde por el tráfico"),
    ("a2_2_natural_spanish", "future targeted recall", "Mañana _____ a estudiar.", "voy", "ir a + infinitive expresses near future", "yo -> voy a", "- Mañana voy a estudiar<br>- Voy a llamar"),
    ("a2_2_natural_spanish", "future targeted recall", "Este verano nosotros _____ a viajar.", "vamos", "ir a + infinitive; nosotros -> vamos", "nosotros -> vamos a", "- Vamos a viajar<br>- Vamos a empezar"),
    ("a2_2_natural_spanish", "future targeted recall", "Creo que ella _____ tarde.", "llegará", "future tense for prediction", "future prediction", "- Ella llegará tarde<br>- Todo saldrá bien"),
    ("a2_2_natural_spanish", "future targeted recall", "Si puedo, te _____ mañana.", "llamaré", "future tense for promise/intention", "future intention", "- Te llamaré mañana<br>- Lo haré después"),
    ("b1_bridge", "subjunctive targeted recall", "Quiero que tú _____.", "vengas", "querer que + subjunctive", "querer que + subjunctive", "- Quiero que vengas<br>- Necesito que me ayudes"),
    ("b1_bridge", "subjunctive targeted recall", "No creo que él _____.", "venga", "no creer que + subjunctive", "doubt/negated belief", "- No creo que venga<br>- No pienso que sea fácil"),
    ("b1_bridge", "subjunctive targeted recall", "Es importante que nosotros _____.", "estudiemos", "es importante que + subjunctive", "impersonal expression + subjunctive", "- Es importante que estudiemos<br>- Es necesario que salgamos"),
    ("b1_bridge", "subjunctive targeted recall", "Busco a alguien que _____ español.", "hable", "unknown/non-specific person + subjunctive", "non-specific antecedent", "- Busco a alguien que hable español<br>- Necesito un lugar que sea tranquilo"),
    ("b1_bridge", "indicative targeted recall", "Creo que él _____.", "viene", "creer que + indicative", "belief/fact", "- Creo que viene<br>- Pienso que es verdad"),
    ("b1_bridge", "indicative targeted recall", "Conozco a alguien que _____ español.", "habla", "known/specific person + indicative", "specific antecedent", "- Conozco a alguien que habla español<br>- Tengo un amigo que vive aquí"),
    ("b1_bridge", "conditional targeted recall", "Si tuviera tiempo, _____ más.", "estudiaría", "si + imperfect subjunctive, conditional result", "conditional result", "- Si tuviera tiempo, estudiaría más<br>- Si pudiera, viajaría"),
    ("b1_bridge", "conditional targeted recall", "Yo _____ más, pero no tengo tiempo.", "estudiaría", "conditional for hypothetical willingness", "would + verb", "- Estudiaría más, pero no tengo tiempo<br>- Compraría el libro, pero es caro"),
    ("b1_bridge", "conditional targeted recall", "¿_____ ayudarme?", "Podrías", "conditional for polite request", "polite request", "- ¿Podrías ayudarme?<br>- ¿Podría hablar contigo?"),
    ("b1_bridge", "conditional targeted recall", "Me _____ vivir en España.", "gustaría", "me gustaría = I would like", "gustaría + infinitive", "- Me gustaría vivir en España<br>- Nos gustaría aprender más"),
    ("b1_bridge", "object pronoun order targeted recall", "Doy el libro a Ana. _____ doy.", "Se lo", "le/les becomes se before lo/la/los/las", "se + lo", "- Se lo doy<br>- Se la envío"),
    ("b1_bridge", "object pronoun order targeted recall", "Compro flores para mis padres. _____ compro.", "Se las", "les becomes se before las", "se + las", "- Se las compro<br>- Se los mando"),
    ("b1_bridge", "object pronoun order targeted recall", "Voy a dar el libro a Ana. Voy a _____.", "dárselo", "pronouns attach to infinitive; accent preserves stress", "infinitive + se + lo", "- Voy a dárselo<br>- Quiero explicárselo"),
    ("b1_bridge", "object pronoun order targeted recall", "Estoy escribiendo la carta a Juan. Estoy _____.", "escribiéndosela", "pronouns attach to gerund; accent preserves stress", "gerund + se + la", "- Estoy escribiéndosela<br>- Está contándomelo"),
    ("b1_bridge", "relative clause targeted recall", "La persona _____ vive aquí es mi amiga.", "que", "que introduces a defining relative clause", "relative pronoun", "- La persona que vive aquí<br>- El libro que compré"),
    ("b1_bridge", "relative clause targeted recall", "El lugar _____ vivo es tranquilo.", "donde", "donde refers to place", "place relative", "- El lugar donde vivo<br>- La ciudad donde nací"),
    ("b1_bridge", "reported speech targeted recall", "Dice que _____ cansado.", "está", "reported speech keeps present when still true", "dice que + present", "- Dice que está cansado<br>- Dice que tiene tiempo"),
    ("b1_bridge", "reported speech targeted recall", "Dijo que _____ cansado.", "estaba", "reported speech shifts present state to imperfect", "dijo que + imperfect", "- Dijo que estaba cansado<br>- Dijo que tenía tiempo"),
]


def _targeted_recall_cards():
    cards = []
    for index, (level, topic_name, front, answer, back, formula, examples) in enumerate(TARGETED_RECALL_CARDS, start=1):
        cards.append(
            _card(
                f"targeted::{level}::{_slug(topic_name)}::{index:03d}",
                level,
                topic_name,
                "typed_contrast",
                "type_exact",
                f"{_front_instruction('Type the Spanish chunk')}<br>{_front_cue('Pattern', formula)}<br>{front}",
                answer,
                back,
                f"Decision rule<br>{html.escape(back)}<br><br>Pattern<br>{html.escape(formula)}",
                examples,
            )
        )
    return cards


def _interleaved_contrast_cards():
    """Cards that mix two competing patterns to train real-time discrimination."""
    cards = []
    for level, topic_name, sent1_front, sent1_ans, sent1_note, sent2_front, sent2_ans, sent2_note in INTERLEAVED_CONTRASTS:
        typed_answer = f"{_derive_blank_answer(sent1_front, sent1_ans)} | {_derive_blank_answer(sent2_front, sent2_ans)}"
        cards.append(
            _card(
                f"interleaved::{level}::{_slug(topic_name)}::1",
                level,
                topic_name,
                "interleaved_contrast",
                "type_compare",
                f"{_front_instruction('Type the correct Spanish form')}<br>{_front_cue('Contrast', topic_name)}<br>{sent1_front}<br><br>{_front_instruction('Then')}<br>{sent2_front}",
                typed_answer,
                f"1. {sent1_ans} — {sent1_note}<br>2. {sent2_ans} — {sent2_note}",
                SPANISH_INTERLEAVED_FORMULAS.get(
                    topic_name,
                    f"Decision rule<br>Choose the form whose grammar function matches the sentence context.<br><br>Pattern<br>{html.escape(topic_name)}",
                ),
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
                    f"{_front_instruction('Complete the Spanish from meaning and context')}<br>{_front_cue('Meaning', eng_text)}<br>{cloze}",
                    target,
                    "Type the missing Spanish word/chunk from the real sentence.",
                    _sentence_target_formula(target),
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
                    _sentence_target_formula(target),
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
    cards.extend(_targeted_recall_cards())
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
