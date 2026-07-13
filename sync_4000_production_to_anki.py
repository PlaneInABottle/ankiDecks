"""Sync production templates and scheduling policy for the 4000 vocabulary decks."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import spanish_deck

import anki_protect


SPANISH_MODEL = "Spanish Recognition"
SPANISH_ROOT = "Spanish 4000 Words"
ENGLISH_ROOT = "4000 Essential English Words"
ENGLISH_MODELS = ("4000 EEW", "4000 EEW Extra")
SPANISH_ACTIVE_LIMIT = 99999
SPANISH_CONTEXT_ACTIVE_LIMIT = 0
ENGLISH_ACTIVE_LIMIT = 99999
BATCH_SIZE = 25
PRODUCTION_FINGERPRINT_FIELD = "ProductionSyncFingerprint"
SPANISH_CONTENT_LEGACY_NAMESPACE = "spanish_4000_content"
SPANISH_PRODUCTION_LEGACY_NAMESPACE = "spanish_4000_production"
ENGLISH_PRODUCTION_LEGACY_NAMESPACE = "english_4000_production"
SOURCE_SUBDECK_NAMES = ["1.Book", "2.Book", "3.Book", "4.Book", "5.Book", "6.Book", "Extra"]
SPANISH_REVIEW_PATH = Path("generated/spanish_full/english_spanish_review.tsv")

SPANISH_EXTRA_FIELDS = [
    "SourceOrder",
    "DifficultyLevel",
    "ProductionCue",
    "ProductionAnswer",
    "ProductionEnabled",
    "SpanishContextCue",
    "SpanishContextProductionEnabled",
    anki_protect.FINGERPRINT_FIELD,
    PRODUCTION_FINGERPRINT_FIELD,
]
SPANISH_CONTENT_FIELDS = [
    "Spanish",
    "PronunciationHint",
    "English",
    "SpanishMeaning",
    "SpanishExample",
    "EnglishMeaning",
    "EnglishExample",
    "Notes",
    "SpanishMeaningEnglish",
    "SpanishExampleEnglish",
    "SpanishArticle",
    "SpanishGender",
    "SpanishNumber",
    "SpanishPartOfSpeech",
    "SpanishForms",
]
ENGLISH_EXTRA_FIELDS = [
    "ProductionSourceID",
    "ProductionCue",
    "ProductionAnswer",
    "ProductionOrder",
    "ProductionLevel",
    "ProductionEnabled",
    PRODUCTION_FINGERPRINT_FIELD,
]
SPANISH_PRODUCTION_FIELDS = [
    "SourceOrder",
    "DifficultyLevel",
    "ProductionCue",
    "ProductionAnswer",
    "ProductionEnabled",
    "SpanishContextCue",
    "SpanishContextProductionEnabled",
]
ENGLISH_PRODUCTION_FIELDS = [
    "ProductionSourceID",
    "ProductionCue",
    "ProductionAnswer",
    "ProductionOrder",
    "ProductionLevel",
    "ProductionEnabled",
]

LEVELS = [
    (0, "Level 0 Survival", 1, 400),
    (1, "Level 1 Concrete", 401, 1000),
    (2, "Level 2 Daily Life", 1001, 1750),
    (3, "Level 3 Abstract Common", 1751, 2550),
    (4, "Level 4 Academic Advanced", 2551, 3350),
    (5, "Level 5 Hard Low Frequency", 3351, 99999),
]

IRREGULAR_ENGLISH_FORMS = {
    "be": {"am", "is", "are", "was", "were", "been", "being"},
    "child": {"children"},
    "do": {"does", "did", "done", "doing"},
    "foot": {"feet"},
    "get": {"gets", "got", "gotten", "getting"},
    "go": {"goes", "went", "gone", "going"},
    "have": {"has", "had", "having"},
    "man": {"men"},
    "mouse": {"mice"},
    "person": {"people"},
    "take": {"takes", "took", "taken", "taking"},
    "tooth": {"teeth"},
    "woman": {"women"},
}


SPANISH_CSS = """
.card {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 18px;
  line-height: 1.32;
  text-align: center;
  color: #111827;
  padding: 8px 10px;
}
.wrap {
  max-width: 820px;
  margin: 0 auto;
}
.target {
  font-size: 31px;
  font-weight: 700;
  letter-spacing: 0;
  margin: 2px 0;
  color: #111827;
}
.pron {
  font-size: 15px;
  font-weight: 600;
  color: #4b5563;
  margin: 0 0 6px;
}
.cue-label,
.label {
  color: #6b7280;
  display: block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .03em;
  margin-bottom: 2px;
  text-transform: uppercase;
}
.production-cue {
  font-size: 24px;
  font-weight: 650;
  margin: 10px 0 8px;
}
.sense-cue {
  color: #6b7280;
  font-size: 14px;
  font-weight: 450;
  line-height: 1.4;
  margin: 8px auto;
  max-width: 680px;
}
.type-note {
  color: #6b7280;
  font-size: 12px;
  margin: 6px 0;
}
.rescue {
  color: #6b7280;
  font-size: 12px;
  margin: 10px auto 0;
  max-width: 680px;
  text-align: left;
}
.rescue summary {
  cursor: pointer;
  font-weight: 700;
  text-align: center;
}
.rescue-content {
  border-top: 1px solid #d1d5db;
  margin-top: 6px;
  padding-top: 6px;
}
.rescue .block {
  margin: 5px 0;
}
.image {
  margin: 4px auto 6px;
}
.image img {
  display: block;
  max-width: 180px;
  max-height: 115px;
  margin: 0 auto;
  border-radius: 5px;
}
.stack {
  margin: 8px auto 0;
  max-width: 700px;
  margin-top: 8px;
  text-align: center;
}
.panel {
  border-top: 1px solid #d1d5db;
  padding-top: 7px;
}
.panel + .panel {
  margin-top: 8px;
}
.primary {
  font-size: 21px;
  font-weight: 650;
  text-align: center;
}
.block {
  margin: 5px 0;
}
.example {
  font-style: italic;
}
.grammar {
  color: #374151;
  font-size: 13px;
  line-height: 1.35;
}
input {
  max-width: 92%;
  color: #111827;
  background: #f9fafb;
}
.card.nightMode,
.nightMode .card { color: #f3f4f6; }
.card.nightMode .target,
.nightMode .card .target,
.card.nightMode .primary,
.nightMode .card .primary,
.card.nightMode input,
.nightMode .card input { color: #ffffff; }
.card.nightMode input,
.nightMode .card input { background: #2a2a2a; }
.card.nightMode .pron,
.nightMode .card .pron,
.card.nightMode .grammar,
.nightMode .card .grammar,
.card.nightMode .type-note,
.nightMode .card .type-note,
.card.nightMode .rescue,
.nightMode .card .rescue { color: #d1d5db; }
.card.nightMode .label,
.nightMode .card .label,
.card.nightMode .cue-label,
.nightMode .card .cue-label { color: #cbd5e1; }
.card.nightMode .panel,
.nightMode .card .panel,
.card.nightMode .rescue-content,
.nightMode .card .rescue-content { border-top-color: #6b7280; }
@media (max-width: 560px) {
  .target { font-size: 28px; }
  .production-cue { font-size: 22px; }
}
"""

ENGLISH_PRODUCTION_CSS = """
.production {
  max-width: 760px;
  margin: 0 auto;
  text-align: center;
}
.production .cue-label,
.production .label {
  color: #6b7280;
  display: block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .03em;
  margin-bottom: 2px;
  text-transform: uppercase;
}
.production .production-cue {
  font-size: 24px;
  font-weight: 650;
  margin: 10px 0 8px;
}
.production .sense-cue,
.production .type-note {
  color: #6b7280;
  font-size: 14px;
  font-weight: 450;
  line-height: 1.4;
  margin: 8px auto;
  max-width: 680px;
}
.production .target {
  font-size: 31px;
  font-weight: 700;
  margin: 8px 0 2px;
}
.production .pron {
  color: #4b5563;
  font-size: 15px;
  font-weight: 600;
}
.production .block {
  margin: 8px auto;
  max-width: 680px;
}
.production .example {
  font-style: italic;
}
.production .image img {
  display: block;
  max-width: 180px;
  max-height: 115px;
  margin: 6px auto;
  border-radius: 5px;
}
"""

SPANISH_RECOGNITION_FRONT = """
<div class="wrap">
  <div class="target">{{Spanish}}</div>
  <div class="pron">{{PronunciationHint}}</div>
</div>
"""

SPANISH_RECOGNITION_BACK = """
<div class="wrap">
  <div class="target">{{Spanish}}</div>
  <div class="pron">{{PronunciationHint}}</div>
  {{#Image}}<div class="image">{{Image}}</div>{{/Image}}
  <div class="stack">
    <div class="panel">
      {{#SpanishMeaning}}<div class="block"><span class="label">Spanish meaning</span>{{SpanishMeaning}}</div>{{/SpanishMeaning}}
      {{#SpanishExample}}<div class="block example"><span class="label">Spanish example</span>{{SpanishExample}}</div>{{/SpanishExample}}
    </div>
    <div class="panel">
      <div class="grammar">
        {{#SpanishPartOfSpeech}}<b>POS:</b> {{SpanishPartOfSpeech}}<br>{{/SpanishPartOfSpeech}}
        {{#SpanishArticle}}<b>Article:</b> {{SpanishArticle}}<br>{{/SpanishArticle}}
        {{#SpanishGender}}<b>Gender:</b> {{SpanishGender}}<br>{{/SpanishGender}}
        {{#SpanishNumber}}<b>Number:</b> {{SpanishNumber}}<br>{{/SpanishNumber}}
        {{#SpanishForms}}<b>Forms:</b> {{SpanishForms}}{{/SpanishForms}}
      </div>
      {{#Notes}}<div class="grammar">{{Notes}}</div>{{/Notes}}
    </div>
    <details class="rescue">
      <summary>English rescue</summary>
      <div class="rescue-content">
        <div class="primary"><span class="label">English</span>{{English}}</div>
        {{#EnglishExample}}<div class="block example"><span class="label">English example</span>{{EnglishExample}}</div>{{/EnglishExample}}
        {{#EnglishMeaning}}<div class="block"><span class="label">English meaning</span>{{EnglishMeaning}}</div>{{/EnglishMeaning}}
      </div>
    </details>
  </div>
</div>
"""

SPANISH_PRODUCTION_FRONT = """
{{#ProductionCue}}
<div class="wrap">
  <span class="cue-label">Produce Spanish</span>
  <div class="production-cue">{{ProductionCue}}</div>
  {{#ProductionAnswer}}
    <div class="type-note">Type the best answer for this sense. Include the article for nouns.</div>
    {{type:ProductionAnswer}}
  {{/ProductionAnswer}}
  {{^ProductionAnswer}}
    <div class="type-note">Say or type one natural answer, then reveal and self-grade. Valid synonyms count.</div>
  {{/ProductionAnswer}}
</div>
{{/ProductionCue}}
"""

SPANISH_PRODUCTION_BACK = """
{{#ProductionCue}}
<div class="wrap">
  {{FrontSide}}
  <div class="target">{{Spanish}}</div>
  {{^ProductionAnswer}}<div class="type-note">Self-grade by meaning and naturalness, not exact wording.</div>{{/ProductionAnswer}}
  <div class="pron">{{PronunciationHint}}</div>
  {{#Image}}<div class="image">{{Image}}</div>{{/Image}}
  <div class="stack">
    <div class="panel">
      {{#SpanishMeaning}}<div class="block"><span class="label">Spanish meaning</span>{{SpanishMeaning}}</div>{{/SpanishMeaning}}
      {{#SpanishExample}}<div class="block example"><span class="label">Spanish example</span>{{SpanishExample}}</div>{{/SpanishExample}}
    </div>
    <div class="panel">
      <div class="grammar">
        {{#SpanishPartOfSpeech}}<b>POS:</b> {{SpanishPartOfSpeech}}<br>{{/SpanishPartOfSpeech}}
        {{#SpanishArticle}}<b>Article:</b> {{SpanishArticle}}<br>{{/SpanishArticle}}
        {{#SpanishForms}}<b>Forms:</b> {{SpanishForms}}{{/SpanishForms}}
      </div>
    </div>
    <details class="rescue">
      <summary>English rescue</summary>
      <div class="rescue-content">
        <div class="primary"><span class="label">English</span>{{English}}</div>
        {{#EnglishExample}}<div class="block example"><span class="label">English example</span>{{EnglishExample}}</div>{{/EnglishExample}}
        {{#EnglishMeaning}}<div class="block"><span class="label">English meaning</span>{{EnglishMeaning}}</div>{{/EnglishMeaning}}
      </div>
    </details>
  </div>
</div>
{{/ProductionCue}}
"""

SPANISH_CONTEXT_PRODUCTION_FRONT = """
{{#SpanishContextProductionEnabled}}
<div class="wrap">
  <span class="cue-label">Type Spanish from Spanish context</span>
  <div class="production-cue">{{SpanishContextCue}}</div>
  {{#ProductionAnswer}}
    <div class="type-note">Use the Spanish context. Include the article for nouns.</div>
    {{type:ProductionAnswer}}
  {{/ProductionAnswer}}
  {{^ProductionAnswer}}
    <div class="type-note">Produce one natural completion, then reveal and self-grade.</div>
  {{/ProductionAnswer}}
</div>
{{/SpanishContextProductionEnabled}}
"""

SPANISH_CONTEXT_PRODUCTION_BACK = """
{{#SpanishContextProductionEnabled}}
<div class="wrap">
  {{FrontSide}}
  <div class="target">{{Spanish}}</div>
  <div class="pron">{{PronunciationHint}}</div>
  {{#Image}}<div class="image">{{Image}}</div>{{/Image}}
  <div class="stack">
    <div class="panel">
      {{#SpanishMeaning}}<div class="block"><span class="label">Spanish meaning</span>{{SpanishMeaning}}</div>{{/SpanishMeaning}}
      {{#SpanishExample}}<div class="block example"><span class="label">Spanish example</span>{{SpanishExample}}</div>{{/SpanishExample}}
    </div>
    <div class="panel">
      <div class="grammar">
        {{#SpanishPartOfSpeech}}<b>POS:</b> {{SpanishPartOfSpeech}}<br>{{/SpanishPartOfSpeech}}
        {{#SpanishArticle}}<b>Article:</b> {{SpanishArticle}}<br>{{/SpanishArticle}}
        {{#SpanishForms}}<b>Forms:</b> {{SpanishForms}}{{/SpanishForms}}
      </div>
    </div>
    <details class="rescue">
      <summary>English rescue</summary>
      <div class="rescue-content">
        <div class="primary"><span class="label">English</span>{{English}}</div>
        {{#EnglishExample}}<div class="block example"><span class="label">English example</span>{{EnglishExample}}</div>{{/EnglishExample}}
        {{#EnglishMeaning}}<div class="block"><span class="label">English meaning</span>{{EnglishMeaning}}</div>{{/EnglishMeaning}}
      </div>
    </details>
  </div>
</div>
{{/SpanishContextProductionEnabled}}
"""

ENGLISH_PRODUCTION_FRONT = """
{{#ProductionCue}}
<div class="wrap production">
  <span class="cue-label">Produce English</span>
  <div class="production-cue">{{ProductionCue}}</div>
  {{#ProductionAnswer}}
    {{type:ProductionAnswer}}
  {{/ProductionAnswer}}
  {{^ProductionAnswer}}
    <div class="type-note">Say or type one natural answer, then reveal and self-grade. Valid synonyms count.</div>
  {{/ProductionAnswer}}
</div>
{{/ProductionCue}}
"""

ENGLISH_PRODUCTION_BACK_MAIN = """
{{#ProductionCue}}
<div class="wrap production">
  {{FrontSide}}
  <div class="target">{{Word}}</div>
  {{^ProductionAnswer}}<div class="type-note">Self-grade by the source sense and naturalness, not exact wording.</div>{{/ProductionAnswer}}
  {{#IPA}}<div class="pron">{{IPA}}</div>{{/IPA}}
  {{#Sound}}{{Sound}}{{/Sound}}
  {{#Image}}<div class="image">{{Image}}</div>{{/Image}}
  {{#Meaning}}<div class="block"><span class="label">Meaning</span>{{Meaning}}</div>{{/Meaning}}
  {{#Example}}<div class="block example"><span class="label">Example</span>{{Example}}</div>{{/Example}}
</div>
{{/ProductionCue}}
"""

ENGLISH_PRODUCTION_BACK_EXTRA = """
{{#ProductionCue}}
<div class="wrap production">
  {{FrontSide}}
  <div class="target">{{English}}</div>
  {{^ProductionAnswer}}<div class="type-note">Self-grade by meaning and naturalness, not exact wording.</div>{{/ProductionAnswer}}
  {{#Am&BrTranscription}}<div class="pron">{{Am&BrTranscription}}</div>{{/Am&BrTranscription}}
  {{#Audio}}{{Audio}}{{/Audio}}
  {{#IMG}}<div class="image">{{IMG}}</div>{{/IMG}}
</div>
{{/ProductionCue}}
"""


def invoke(action: str, **params):
    payload = json.dumps({"action": action, "params": params, "version": 6}).encode("utf-8")
    request = urllib.request.Request("http://127.0.0.1:8765", payload, headers={"Content-Type": "application/json"})
    for attempt in range(3):
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("error"):
            return result["result"]
        if result["error"] != "collection is not available" or attempt == 2:
            raise RuntimeError(result["error"])
        time.sleep(2)
    raise RuntimeError("collection is not available")


def invoke_multi(actions: List[Dict[str, object]], batch_size: int = BATCH_SIZE) -> List[object]:
    results: List[object] = []
    for offset in range(0, len(actions), batch_size):
        batch = actions[offset : offset + batch_size]
        payload = json.dumps({"action": "multi", "params": {"actions": batch}, "version": 6}).encode("utf-8")
        request = urllib.request.Request(
            "http://127.0.0.1:8765",
            payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
        if result.get("error"):
            raise RuntimeError(result["error"])
        for item in result["result"]:
            if isinstance(item, dict) and item.get("error"):
                raise RuntimeError(item["error"])
            if isinstance(item, dict) and "result" in item:
                results.append(item.get("result"))
            else:
                results.append(item)
    return results


def chunks(values: List[int], size: int = 500) -> Iterable[List[int]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(" ".join(text.split()))


def level_for_order(order: int) -> str:
    for _, label, start, end in LEVELS:
        if start <= order <= end:
            return label
    return LEVELS[-1][1]


def level_deck(root: str, order: int) -> str:
    return f"{root}::{level_for_order(order)}"


def source_sort_rank(deck: str) -> int:
    for index in range(1, 7):
        if deck.endswith(f"::{index}.Book"):
            return index
    if deck.endswith("::Extra"):
        return 7
    return 99


def source_card_number(value: str) -> Tuple[int, ...]:
    numbers = [int(part) for part in re.findall(r"\d+", value or "")]
    return tuple(numbers or [999999])


def difficulty_order(source_rows: List[Dict[str, str]]) -> Dict[str, int]:
    source_file_indexes = {id(row): index for index, row in enumerate(source_rows, start=1)}
    sorted_rows = sorted(
        source_rows,
        key=lambda row: (
            source_sort_rank(row.get("deck", "")),
            source_file_indexes.get(id(row), 999999),
            source_card_number(row.get("card_number", "")),
            strip_html(row.get("english_word", "")).lower(),
            strip_html(row.get("english_meaning", "")).lower(),
        ),
    )
    order_map: Dict[str, int] = {}
    for index, row in enumerate(sorted_rows, start=1):
        order_map[source_id_from_row(row)] = index
        source_file_index = source_file_indexes.get(id(row))
        if source_file_index is not None:
            order_map[
                "::".join(
                    [
                        row.get("deck", ""),
                        f"row-{source_file_index:04d}",
                        strip_html(row.get("english_word", "")).lower(),
                    ]
                )
            ] = index
    return order_map


def source_id_from_row(row: Dict[str, str]) -> str:
    return "::".join(
        [
            row.get("deck", ""),
            row.get("card_number", ""),
            strip_html(row.get("english_word", "")).lower(),
        ]
    )


def source_id_from_spanish_note(fields: Dict[str, Dict[str, str]]) -> str:
    source_id = fields.get("SourceID", {}).get("value", "")
    parts = source_id.split("::")
    if len(parts) < 4:
        return source_id
    deck = "::".join(parts[:2])
    card_number = parts[2]
    english = parts[3].lower()
    return "::".join([deck, card_number, english])


def source_id_from_english_note(note: Dict[str, object]) -> str:
    fields = note.get("fields", {})
    stable_id = fields.get("ProductionSourceID", {}).get("value", "")
    if stable_id:
        return stable_id
    deck = note.get("cardsInfoDeckName") or ""
    if not deck:
        cards = note.get("cards", [])
        if cards:
            deck = invoke("cardsInfo", cards=[cards[0]])[0]["deckName"]
    if deck.endswith("::Extra"):
        word = fields.get("English", {}).get("value", "")
        card_number = fields.get("№", {}).get("value", "")
    else:
        word = fields.get("Word", {}).get("value", "")
        card_number = ""
    return "::".join([str(deck), str(card_number), strip_html(str(word)).lower()])


def ensure_fields(model_name: str, fields: Iterable[str]) -> None:
    existing = invoke("modelFieldNames", modelName=model_name)
    for field in fields:
        if field not in existing:
            invoke("modelFieldAdd", modelName=model_name, fieldName=field)
            existing.append(field)


def ensure_template(
    model_name: str, name: str, front: str, back: str, update_existing: bool = False
) -> None:
    templates = invoke("modelTemplates", modelName=model_name)
    if name not in templates:
        invoke("modelTemplateAdd", modelName=model_name, template={"Name": name, "Front": front, "Back": back})
        return
    if not update_existing:
        return
    templates[name] = {"Front": front, "Back": back}
    invoke("updateModelTemplates", model={"name": model_name, "templates": templates})


def ensure_models(update_existing: bool = False) -> None:
    ensure_fields(SPANISH_MODEL, SPANISH_EXTRA_FIELDS)
    if update_existing:
        invoke("updateModelStyling", model={"name": SPANISH_MODEL, "css": SPANISH_CSS})
    ensure_template(
        SPANISH_MODEL, "Recognition", SPANISH_RECOGNITION_FRONT, SPANISH_RECOGNITION_BACK, update_existing
    )
    ensure_template(
        SPANISH_MODEL, "Production", SPANISH_PRODUCTION_FRONT, SPANISH_PRODUCTION_BACK, update_existing
    )
    ensure_template(
        SPANISH_MODEL,
        "Spanish Context Production",
        SPANISH_CONTEXT_PRODUCTION_FRONT,
        SPANISH_CONTEXT_PRODUCTION_BACK,
        update_existing,
    )
    for model_name in ENGLISH_MODELS:
        ensure_fields(model_name, ENGLISH_EXTRA_FIELDS)
        try:
            styling = invoke("modelStyling", modelName=model_name)
            css = styling.get("css", "")
            if update_existing and ".production .sense-cue" not in css:
                invoke("updateModelStyling", model={"name": model_name, "css": css + "\n" + ENGLISH_PRODUCTION_CSS})
        except Exception:
            pass
        ensure_template(
            model_name,
            "Production",
            ENGLISH_PRODUCTION_FRONT,
            ENGLISH_PRODUCTION_BACK_EXTRA if model_name.endswith("Extra") else ENGLISH_PRODUCTION_BACK_MAIN,
            update_existing,
        )


def get_notes(query: str) -> List[Dict[str, object]]:
    note_ids = invoke("findNotes", query=query)
    if not note_ids:
        return []
    return invoke("notesInfo", notes=note_ids)


def spanish_base_production_cue(fields: Dict[str, Dict[str, str]]) -> str:
    english = strip_html(fields.get("English", {}).get("value", ""))
    pos = fields.get("SpanishPartOfSpeech", {}).get("value", "")
    if pos == "noun" and english and not english.lower().startswith(("the ", "a ", "an ")):
        return f"the {english}"
    return english


def _mask_english_answer(text: str, answer: str) -> str:
    """Mask a requested English answer and common inflections in a clue."""
    plain = strip_html(text)
    target = strip_html(answer).strip()
    if not plain or not target:
        return plain

    tokens = target.split()
    stem = tokens[-1]
    lower = stem.lower()
    forms = {stem, f"{stem}s", f"{stem}ed", f"{stem}ing"}
    forms.update(IRREGULAR_ENGLISH_FORMS.get(lower, set()))
    if lower.endswith(("s", "x", "z", "ch", "sh", "o")):
        forms.add(f"{stem}es")
    if lower.endswith("e"):
        forms.update({f"{stem}d", f"{stem[:-1]}ing"})
    if len(stem) > 1 and lower.endswith("y") and lower[-2] not in "aeiou":
        forms.update({f"{stem[:-1]}ies", f"{stem[:-1]}ied"})
    if (
        len(stem) >= 3
        and lower[-1] not in "aeiouwxy"
        and lower[-2] in "aeiou"
        and lower[-3] not in "aeiou"
    ):
        forms.update({f"{stem}{stem[-1]}ed", f"{stem}{stem[-1]}ing"})

    prefix = " ".join(tokens[:-1])
    variants = {f"{prefix} {form}".strip() for form in forms}
    masked = plain
    for variant in sorted(variants, key=len, reverse=True):
        pattern = rf"(?<![\w']){re.escape(variant)}(?:['’]s)?(?![\w'])"
        masked = re.sub(pattern, "_____", masked, flags=re.IGNORECASE)
    return masked


def _source_sense_html(label: str, text: str) -> str:
    plain = " ".join(strip_html(text).split())
    if not plain:
        return ""
    return (
        f'<div class="sense-cue"><span class="label">{html.escape(label)}</span>'
        f"{html.escape(plain)}</div>"
    )


def spanish_production_cue(fields: Dict[str, Dict[str, str]]) -> str:
    """Build an English production cue with enough source context to fix the sense."""
    primary = spanish_base_production_cue(fields)
    pos = strip_html(fields.get("SpanishPartOfSpeech", {}).get("value", ""))
    meaning = fields.get("EnglishMeaning", {}).get("value", "")
    example = fields.get("EnglishExample", {}).get("value", "")
    primary_html = html.escape(primary)
    if pos:
        primary_html += f' <span class="sense-cue">({html.escape(pos)})</span>'
    sense = _source_sense_html("Context", meaning or example)
    return f'<div class="production-primary">{primary_html}</div>{sense}'


def english_production_cue(
    turkish_cue: str,
    answer: str,
    reviewed_meaning: str = "",
    reviewed_example: str = "",
) -> str:
    """Build a Turkish cue plus a reviewed, answer-masked sense discriminator."""
    primary = html.escape(strip_html(turkish_cue))
    sense_text = _mask_english_answer(reviewed_meaning or reviewed_example, answer)
    sense = _source_sense_html("Bağlam", sense_text)
    return f'<div class="production-primary">{primary}</div>{sense}'


def _ambiguity_key(value: str) -> str:
    return " ".join(strip_html(value).lower().split())


def spanish_target_variants(spanish: str) -> List[str]:
    plain = strip_html(spanish).strip()
    variants = {plain}
    tokens = plain.split()
    if tokens and tokens[0].lower() in {"el", "la", "los", "las", "un", "una", "unos", "unas"}:
        variants.add(" ".join(tokens[1:]))
    return sorted((variant for variant in variants if variant), key=len, reverse=True)


def mask_spanish_target(text: str, spanish: str) -> str:
    masked = strip_html(text)
    for variant in spanish_target_variants(spanish):
        masked = re.sub(re.escape(variant), "_____", masked, flags=re.IGNORECASE)
    return masked


def spanish_context_cue(fields: Dict[str, Dict[str, str]]) -> str:
    spanish = fields.get("Spanish", {}).get("value", "")
    meaning = mask_spanish_target(fields.get("SpanishMeaning", {}).get("value", ""), spanish)
    example = mask_spanish_target(fields.get("SpanishExample", {}).get("value", ""), spanish)
    parts = []
    if meaning:
        parts.append(f'<div class="block"><span class="label">Significado</span>{html.escape(meaning)}</div>')
    if example:
        parts.append(f'<div class="block example"><span class="label">Ejemplo</span>{html.escape(example)}</div>')
    return "".join(parts)


def update_note_fields_many(updates: List[Tuple[int, Dict[str, str]]]) -> None:
    actions = [
        {"action": "updateNoteFields", "params": {"note": {"id": note_id, "fields": fields}}}
        for note_id, fields in updates
    ]
    invoke_multi(actions)


def card_maps_for_notes(notes: List[Dict[str, object]]) -> Dict[int, Dict[int, int]]:
    card_ids: List[int] = []
    for note in notes:
        card_ids.extend(note.get("cards", []))
    cards = []
    for batch in chunks(card_ids):
        cards.extend(invoke("cardsInfo", cards=batch))
    by_note: Dict[int, Dict[int, int]] = {}
    for card in cards:
        by_note.setdefault(card["note"], {})[card["ord"]] = card["cardId"]
    return by_note


def apply_card_plan(deck_cards: Dict[str, List[int]], active_cards: List[int], suspended_cards: List[int]) -> None:
    for deck_name in sorted(deck_cards):
        cards = deck_cards[deck_name]
        if cards:
            invoke("changeDeck", cards=cards, deck=deck_name)
    for batch in chunks(active_cards):
        if batch:
            invoke("unsuspend", cards=batch)
    for batch in chunks(suspended_cards):
        if batch:
            invoke("suspend", cards=batch)


def cleanup_empty_source_decks() -> List[str]:
    deleted: List[str] = []
    deck_names = set(invoke("deckNames"))
    candidates = [
        f"{root}::{name}"
        for root in (SPANISH_ROOT, ENGLISH_ROOT)
        for name in SOURCE_SUBDECK_NAMES
    ]
    for deck_name in candidates:
        if deck_name not in deck_names:
            continue
        card_ids = invoke("findCards", query=f'deck:"{deck_name}"')
        if card_ids:
            continue
        invoke("deleteDecks", decks=[deck_name], cardsToo=True)
        deleted.append(deck_name)
    return deleted


def sync_spanish(
    order_map: Dict[str, int], active_limit: int, context_active_limit: int, force: bool = False
) -> Dict[str, int]:
    notes = get_notes(f'note:"{SPANISH_MODEL}"')
    updates: List[Tuple[int, Dict[str, str]]] = []
    note_orders: Dict[int, int] = {}
    updated = 0
    recognition_suspended = 0
    production_suspended = 0
    context_suspended = 0
    skipped_locked = 0
    auto_locked = 0
    answers_by_cue: Dict[str, set[str]] = defaultdict(set)
    for note in notes:
        fields = note["fields"]
        base_cue = _ambiguity_key(spanish_base_production_cue(fields))
        answer = _ambiguity_key(fields.get("Spanish", {}).get("value", ""))
        if base_cue and answer:
            answers_by_cue[base_cue].add(answer)
    for note in notes:
        fields = note["fields"]
        key = source_id_from_spanish_note(fields)
        order = order_map.get(key, 99999)
        note_orders[note["noteId"]] = order
        level = level_for_order(order)
        cue = spanish_production_cue(fields)
        answer = strip_html(fields.get("Spanish", {}).get("value", ""))
        base_cue = _ambiguity_key(spanish_base_production_cue(fields))
        exact_answer = "" if len(answers_by_cue.get(base_cue, set())) > 1 else answer
        context_enabled = "yes" if order <= context_active_limit else ""
        legacy_source_fields = {
            "SourceOrder": str(order),
            "DifficultyLevel": level,
            "ProductionCue": spanish_base_production_cue(fields),
            "ProductionAnswer": answer,
            "ProductionEnabled": "yes",
            "SpanishContextCue": spanish_context_cue(fields),
            "SpanishContextProductionEnabled": context_enabled,
        }
        source_fields = {
            "SourceOrder": str(order),
            "DifficultyLevel": level,
            "ProductionCue": cue,
            "ProductionAnswer": exact_answer,
            "ProductionEnabled": "yes",
            "SpanishContextCue": spanish_context_cue(fields),
            "SpanishContextProductionEnabled": context_enabled,
        }
        preserve_content = not force and anki_protect.note_is_locked(note.get("tags", []))
        if preserve_content:
            skipped_locked += 1
        elif not force and anki_protect.note_has_untracked_edits(
            fields,
            source_fields,
            SPANISH_PRODUCTION_FIELDS,
            PRODUCTION_FINGERPRINT_FIELD,
            (
                *anki_protect.legacy_fingerprints(
                    SPANISH_PRODUCTION_LEGACY_NAMESPACE, key
                ),
                anki_protect.content_fingerprint(
                    legacy_source_fields, SPANISH_PRODUCTION_FIELDS
                ),
            ),
        ):
            invoke("addTags", notes=[note["noteId"]], tags=anki_protect.LOCKED_TAG)
            auto_locked += 1
        else:
            updates.append(
                (
                    note["noteId"],
                    anki_protect.source_fields_with_fingerprint(
                        source_fields,
                        SPANISH_PRODUCTION_FIELDS,
                        PRODUCTION_FINGERPRINT_FIELD,
                    ),
                )
            )
            updated += 1
    update_note_fields_many(updates)
    notes = get_notes(f'note:"{SPANISH_MODEL}"')
    note_cards = card_maps_for_notes(notes)
    deck_cards: Dict[str, List[int]] = {}
    active_cards: List[int] = []
    suspended_cards: List[int] = []
    for note in notes:
        order = note_orders.get(note["noteId"], 99999)
        cards = note_cards.get(note["noteId"], {})
        deck_name = level_deck(SPANISH_ROOT, order)
        if 0 in cards:
            deck_cards.setdefault(deck_name, []).append(cards[0])
            suspended_cards.append(cards[0])
            recognition_suspended += 1
        if 1 in cards:
            production_active = order <= active_limit
            deck_cards.setdefault(deck_name, []).append(cards[1])
            (active_cards if production_active else suspended_cards).append(cards[1])
            production_suspended += 0 if production_active else 1
        if 2 in cards:
            context_active = order <= context_active_limit
            deck_cards.setdefault(deck_name, []).append(cards[2])
            (active_cards if context_active else suspended_cards).append(cards[2])
            context_suspended += 0 if context_active else 1
    apply_card_plan(deck_cards, active_cards, suspended_cards)
    return {
        "updated_notes": updated,
        "recognition_suspended": recognition_suspended,
        "production_suspended": production_suspended,
        "context_suspended": context_suspended,
        "skipped_locked": skipped_locked,
        "auto_locked": auto_locked,
    }


def load_spanish_review_rows(path: Path, source_rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    source_indexes = {
        (
            row.get("deck", ""),
            row.get("card_number", ""),
            strip_html(row.get("english_word", "")).lower(),
        ): index
        for index, row in enumerate(source_rows, start=1)
    }
    rows_by_key: Dict[str, Dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            english = strip_html(row.get("English", "")).lower()
            source_deck = row.get("Source Deck", "")
            source_card = row.get("Source Card", "")
            keys = [f"{source_deck}::{source_card}::{english}"]
            source_index = source_indexes.get((source_deck, source_card, english))
            if source_index is not None:
                keys.append(f"{source_deck}::row-{source_index:04d}::{english}")
            if not source_card:
                keys.append(f"{source_deck}::::{english}")
            for key in keys:
                rows_by_key[key] = row
    return rows_by_key


def spanish_content_fields(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "Spanish": row.get("Spanish", ""),
        "PronunciationHint": row.get("Pronunciation Hint", ""),
        "English": row.get("English", ""),
        "SpanishMeaning": row.get("Spanish Meaning", ""),
        "SpanishExample": row.get("Spanish Example", ""),
        "EnglishMeaning": row.get("English Meaning", ""),
        "EnglishExample": row.get("English Example", ""),
        "Notes": row.get("Notes", ""),
        "SpanishMeaningEnglish": row.get("Spanish Meaning (English)", ""),
        "SpanishExampleEnglish": row.get("Spanish Example (English)", ""),
        "SpanishArticle": row.get("Spanish Article", ""),
        "SpanishGender": row.get("Spanish Gender", ""),
        "SpanishNumber": row.get("Spanish Number", ""),
        "SpanishPartOfSpeech": row.get("Spanish Part of Speech", ""),
        "SpanishForms": row.get("Spanish Forms", ""),
    }


def sync_spanish_content(review_path: Path, source_rows: List[Dict[str, str]], force: bool = False) -> Dict[str, int]:
    review_rows = load_spanish_review_rows(review_path, source_rows)
    if not review_rows:
        return {"updated_notes": 0, "missing_review_rows": 0}
    notes = get_notes(f'note:"{SPANISH_MODEL}"')
    updates: List[Tuple[int, Dict[str, str]]] = []
    missing = 0
    skipped_locked = 0
    auto_locked = 0
    for note in notes:
        if not force and anki_protect.note_is_locked(note.get("tags", [])):
            skipped_locked += 1
            continue
        key = source_id_from_spanish_note(note["fields"])
        row = review_rows.get(key)
        if not row:
            missing += 1
            continue
        source_fields = spanish_content_fields(row)
        if not force and anki_protect.note_has_untracked_edits(
            note.get("fields", {}),
            source_fields,
            SPANISH_CONTENT_FIELDS,
            legacy_fingerprints=anki_protect.legacy_fingerprints(
                SPANISH_CONTENT_LEGACY_NAMESPACE, key
            ),
        ):
            invoke("addTags", notes=[note["noteId"]], tags=anki_protect.LOCKED_TAG)
            auto_locked += 1
            continue
        updates.append(
            (
                note["noteId"],
                anki_protect.source_fields_with_fingerprint(source_fields, SPANISH_CONTENT_FIELDS),
            )
        )
    update_note_fields_many(updates)
    return {
        "updated_notes": len(updates),
        "missing_review_rows": missing,
        "skipped_locked": skipped_locked,
        "auto_locked": auto_locked,
    }


def load_turkish_rows(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["SourceID"]: row for row in csv.DictReader(handle, delimiter="\t")}


def load_turkish_cues(path: Path) -> Dict[str, str]:
    return {
        source_id: row.get("TurkishCue", "").strip()
        for source_id, row in load_turkish_rows(path).items()
        if row.get("TurkishCue", "").strip()
    }


def sync_english(
    order_map: Dict[str, int],
    cue_map: Dict[str, str],
    active_limit: int,
    force: bool = False,
    sense_rows: Dict[str, Dict[str, str]] | None = None,
) -> Dict[str, int]:
    sense_rows = sense_rows or {}
    notes: List[Dict[str, object]] = []
    seen_note_ids = set()
    for model_name in ENGLISH_MODELS:
        model_note_ids = invoke("findNotes", query=f'note:"{model_name}"')
        for note in invoke("notesInfo", notes=model_note_ids):
            if note["noteId"] in seen_note_ids:
                continue
            seen_note_ids.add(note["noteId"])
            notes.append(note)
    first_card_ids = [note.get("cards", [None])[0] for note in notes if note.get("cards")]
    deck_by_card = {}
    for batch in chunks(first_card_ids):
        for card in invoke("cardsInfo", cards=batch):
            deck_by_card[card["cardId"]] = card["deckName"]
    for note in notes:
        cards = note.get("cards", [])
        if cards:
            note["cardsInfoDeckName"] = deck_by_card.get(cards[0], "")
    updated = 0
    missing_cues = 0
    recognition_suspended = 0
    production_suspended = 0
    updates: List[Tuple[int, Dict[str, str]]] = []
    note_orders: Dict[int, int] = {}
    note_has_cue: Dict[int, bool] = {}
    skipped_locked = 0
    auto_locked = 0
    answers_by_cue: Dict[str, set[str]] = defaultdict(set)
    note_answers: Dict[int, str] = {}
    for note in notes:
        fields = note.get("fields", {})
        answer = strip_html(
            fields.get("Word", fields.get("English", {"value": ""})).get("value", "")
        )
        note_answers[note["noteId"]] = answer
        raw_cue = cue_map.get(source_id_from_english_note(note), "")
        cue_key = _ambiguity_key(raw_cue)
        if cue_key and answer:
            answers_by_cue[cue_key].add(_ambiguity_key(answer))
    for note in notes:
        key = source_id_from_english_note(note)
        order = order_map.get(key, 99999)
        raw_cue = cue_map.get(key, "")
        note_orders[note["noteId"]] = order
        note_has_cue[note["noteId"]] = bool(raw_cue)
        fields = note.get("fields", {})
        answer = note_answers.get(note["noteId"], "")
        sense_row = sense_rows.get(key, {})
        cue = (
            english_production_cue(
                raw_cue,
                answer,
                sense_row.get("EnglishMeaning", ""),
                sense_row.get("EnglishExample", ""),
            )
            if raw_cue
            else ""
        )
        cue_key = _ambiguity_key(raw_cue)
        exact_answer = "" if len(answers_by_cue.get(cue_key, set())) > 1 else answer
        if not raw_cue:
            missing_cues += 1
        legacy_source_fields = {
            "ProductionSourceID": key,
            "ProductionCue": raw_cue,
            "ProductionAnswer": answer,
            "ProductionOrder": str(order),
            "ProductionLevel": level_for_order(order),
            "ProductionEnabled": "yes" if raw_cue else "",
        }
        source_fields = {
            "ProductionSourceID": key,
            "ProductionCue": cue,
            "ProductionAnswer": exact_answer,
            "ProductionOrder": str(order),
            "ProductionLevel": level_for_order(order),
            "ProductionEnabled": "yes" if cue else "",
        }
        fields = note.get("fields", {})
        preserve_content = not force and anki_protect.note_is_locked(note.get("tags", []))
        if preserve_content:
            skipped_locked += 1
        elif not force and anki_protect.note_has_untracked_edits(
            fields,
            source_fields,
            ENGLISH_PRODUCTION_FIELDS,
            PRODUCTION_FINGERPRINT_FIELD,
            (
                *anki_protect.legacy_fingerprints(
                    ENGLISH_PRODUCTION_LEGACY_NAMESPACE, key
                ),
                anki_protect.content_fingerprint(
                    legacy_source_fields, ENGLISH_PRODUCTION_FIELDS
                ),
            ),
        ):
            invoke("addTags", notes=[note["noteId"]], tags=anki_protect.LOCKED_TAG)
            auto_locked += 1
        else:
            updates.append(
                (
                    note["noteId"],
                    anki_protect.source_fields_with_fingerprint(
                        source_fields,
                        ENGLISH_PRODUCTION_FIELDS,
                        PRODUCTION_FINGERPRINT_FIELD,
                    ),
                )
            )
            updated += 1
    update_note_fields_many(updates)
    notes = [note for model_name in ENGLISH_MODELS for note in get_notes(f'note:"{model_name}"')]
    note_cards = card_maps_for_notes(notes)
    deck_cards: Dict[str, List[int]] = {}
    active_cards: List[int] = []
    suspended_cards: List[int] = []
    for note in notes:
        order = note_orders.get(note["noteId"], 99999)
        has_cue = note_has_cue.get(note["noteId"], False)
        cards = note_cards.get(note["noteId"], {})
        deck_name = level_deck(ENGLISH_ROOT, order)
        if 0 in cards:
            deck_cards.setdefault(deck_name, []).append(cards[0])
            suspended_cards.append(cards[0])
            recognition_suspended += 1
        if 1 in cards:
            production_active = has_cue and order <= active_limit
            deck_cards.setdefault(deck_name, []).append(cards[1])
            (active_cards if production_active else suspended_cards).append(cards[1])
            production_suspended += 0 if production_active else 1
    apply_card_plan(deck_cards, active_cards, suspended_cards)
    return {
        "updated_notes": updated,
        "missing_cues": missing_cues,
        "recognition_suspended": recognition_suspended,
        "production_suspended": production_suspended,
        "skipped_locked": skipped_locked,
        "auto_locked": auto_locked,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync 4000 vocabulary production cards to Anki.")
    parser.add_argument("--source", default="4000 Essential English Words.txt")
    parser.add_argument("--turkish-cues", default="generated/english_4000/english_turkish_production.tsv")
    parser.add_argument("--active-limit", type=int, help="Set the same active word limit for both English and Spanish.")
    parser.add_argument("--spanish-active-limit", type=int, default=SPANISH_ACTIVE_LIMIT)
    parser.add_argument("--spanish-context-active-limit", type=int, default=SPANISH_CONTEXT_ACTIVE_LIMIT)
    parser.add_argument("--english-active-limit", type=int, default=ENGLISH_ACTIVE_LIMIT)
    parser.add_argument("--spanish-only", action="store_true")
    parser.add_argument("--english-only", action="store_true")
    parser.add_argument("--cleanup-old-decks-only", action="store_true")
    parser.add_argument("--sync-spanish-content", action="store_true")
    parser.add_argument("--spanish-review", default=str(SPANISH_REVIEW_PATH))
    parser.add_argument("--force", action="store_true", help="Overwrite notes even if tagged locked (manual edits).")
    parser.add_argument("--update-models", action="store_true", help="Replace existing production templates and CSS.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    invoke("version")
    if args.cleanup_old_decks_only:
        print(json.dumps({"deleted_empty_source_decks": cleanup_empty_source_decks()}, ensure_ascii=False, indent=2))
        return 0
    source_rows = spanish_deck.parse_source_deck(args.source)
    order_map = difficulty_order(source_rows)
    ensure_models(update_existing=args.update_models)
    spanish_active_limit = args.active_limit if args.active_limit is not None else args.spanish_active_limit
    spanish_context_active_limit = args.active_limit if args.active_limit is not None else args.spanish_context_active_limit
    english_active_limit = args.active_limit if args.active_limit is not None else args.english_active_limit
    result: Dict[str, object] = {
        "spanish_active_limit": spanish_active_limit,
        "spanish_context_active_limit": spanish_context_active_limit,
        "english_active_limit": english_active_limit,
    }
    if not args.english_only:
        if args.sync_spanish_content:
            result["spanish_content"] = sync_spanish_content(Path(args.spanish_review), source_rows, force=args.force)
        result["spanish"] = sync_spanish(
            order_map, spanish_active_limit, spanish_context_active_limit, force=args.force
        )
    if not args.spanish_only:
        turkish_rows = load_turkish_rows(Path(args.turkish_cues))
        result["english"] = sync_english(
            order_map,
            {
                source_id: row.get("TurkishCue", "").strip()
                for source_id, row in turkish_rows.items()
                if row.get("TurkishCue", "").strip()
            },
            english_active_limit,
            force=args.force,
            sense_rows=turkish_rows,
        )
    result["deleted_empty_source_decks"] = cleanup_empty_source_decks()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
