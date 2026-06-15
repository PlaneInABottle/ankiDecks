import argparse
import csv
import html
import io
import re
from pathlib import Path


SOURCE_PATH = Path("generated/phrases/english_natural_phrases_reviewed.tsv")

LEVELS = [
    {"id": "level_1", "name": "Level 1 - Everyday Core"},
    {"id": "level_2", "name": "Level 2 - Daily Flow"},
    {"id": "level_3", "name": "Level 3 - Work & Social"},
    {"id": "level_4", "name": "Level 4 - Natural Idioms"},
    {"id": "level_5", "name": "Level 5 - B2/C1 Precision"},
    {"id": "level_6", "name": "Level 6 - C2 Native Precision"},
]


def _normalize_level(value):
    value = str(value).strip().lower()
    if value.startswith("level_"):
        return value
    if value.startswith("level "):
        return "level_" + value.split()[-1]
    if value.isdigit():
        return f"level_{value}"
    raise ValueError(f"Invalid level: {value}")


def _html_list(examples):
    parts = [part.strip() for part in re.split(r"\s+\|\s+", examples) if part.strip()]
    return "<br>".join(f"- {part}" for part in parts)


def _front_html(front, phrase):
    escaped_front = html.escape(front)
    exact_phrase = phrase.strip()
    if exact_phrase.lower().startswith("to "):
        exact_phrase = exact_phrase[3:]
    if not any(token in exact_phrase.lower() for token in ("something", "yourself", "your ")):
        exact_pattern = re.compile(rf"\b({re.escape(html.escape(exact_phrase))})\b", re.IGNORECASE)
        if exact_pattern.search(escaped_front):
            return exact_pattern.sub(r'<span class="target-phrase">\1</span>', escaped_front, count=1)
    words = [word for word in re.findall(r"[A-Za-z']+", phrase) if word.lower() not in {"to"}]
    candidates = sorted({word for word in words if len(word) > 2}, key=len, reverse=True)
    for word in candidates:
        pattern = re.compile(rf"\b({re.escape(word)})\b", re.IGNORECASE)
        if pattern.search(escaped_front):
            return pattern.sub(r'<span class="target-phrase">\1</span>', escaped_front, count=1)
    return escaped_front


def _tags(level, phrase, raw_tags):
    base = ["english_phrases", "natural_phrases", level]
    raw = [
        tag.strip().lower().replace(" ", "_")
        for tag in re.split(r"[;, ]+", raw_tags or "")
        if tag.strip()
    ]
    phrase_tag = re.sub(r"[^a-z0-9]+", "_", phrase.lower()).strip("_")
    return " ".join(dict.fromkeys(base + raw + [phrase_tag]))


def load_cards(source_path=SOURCE_PATH):
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Missing phrase source TSV: {source}")

    cards = []
    with source.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        expected = {"SourceID", "Level", "Phrase", "Front", "Meaning", "Examples", "Tags"}
        legacy_expected = {"Level", "Phrase", "Front", "Meaning", "Examples", "Tags"}
        fieldnames = set(reader.fieldnames or [])
        if fieldnames != expected and fieldnames != legacy_expected:
            raise ValueError(f"Unexpected columns: {reader.fieldnames}")

        for index, row in enumerate(reader, start=1):
            level = _normalize_level(row["Level"])
            phrase = row["Phrase"].strip()
            front = row["Front"].strip()
            meaning = row["Meaning"].strip()
            examples = row["Examples"].strip()
            source_id = row.get("SourceID", "").strip()
            if not source_id:
                source_id = f"en_phrase_{index:03d}_{re.sub(r'[^a-z0-9]+', '_', phrase.lower()).strip('_')}"
            if not all([phrase, front, meaning, examples]):
                raise ValueError(f"Blank required field at row {index}")
            cards.append(
                {
                    "source_id": source_id,
                    "level": level,
                    "phrase": phrase,
                    "front": front,
                    "front_html": _front_html(front, phrase),
                    "meaning": meaning,
                    "examples": examples,
                    "tags": _tags(level, phrase, row.get("Tags", "")),
                }
            )
    return cards


def validate_cards(cards):
    errors = []
    seen_phrases = set()
    seen_fronts = set()
    valid_levels = {level["id"] for level in LEVELS}
    for card in cards:
        phrase_key = card["phrase"].lower()
        front_key = card["front"].lower()
        if phrase_key in seen_phrases:
            errors.append(f"Duplicate phrase: {card['phrase']}")
        if front_key in seen_fronts:
            errors.append(f"Duplicate front: {card['front']}")
        seen_phrases.add(phrase_key)
        seen_fronts.add(front_key)
        if card["level"] not in valid_levels:
            errors.append(f"Invalid level for {card['phrase']}: {card['level']}")
        if not _front_contains_phrase_core(card["phrase"], card["front"]):
            errors.append(f"Front does not contain phrase: {card['phrase']}")
        if "she said" in card["front"].lower() and "natural moment" in card["front"].lower():
            errors.append(f"Generic front remains: {card['phrase']}")
        if "common natural connector phrase" in card["meaning"].lower():
            errors.append(f"Generic meaning remains: {card['phrase']}")
        if "try using" in card["examples"].lower():
            errors.append(f"Generic example remains: {card['phrase']}")
        generic_patterns = [
            "sounds natural",
            "natural moment",
            "during sending",
            "during starting",
            "you can hear",
            "the manager said",
            "our team used",
            "in a polished email",
            "get off before the meeting",
            "good morning\" used naturally when meeting someone after a long day",
            "good night\" at the start of a conversation",
        ]
        for pattern in generic_patterns:
            if pattern in (card["front"] + " " + card["examples"]).lower():
                errors.append(f"Generic or mismatched context remains for {card['phrase']}: {pattern}")
        example_count = len([part for part in re.split(r"\s+\|\s+|;\s+", card["examples"]) if part.strip()])
        if example_count < 2:
            errors.append(f"Too few examples: {card['phrase']}")
    return errors


def _front_contains_phrase_core(phrase, front):
    front_words = set(re.findall(r"[a-z']+", front.lower()))
    stop_words = {
        "to",
        "be",
        "a",
        "an",
        "the",
        "of",
        "for",
        "at",
        "in",
        "on",
        "with",
        "your",
        "you",
        "something",
        "yourself",
    }
    variants = {
        "miss": {"miss", "missed", "misses", "missing"},
        "beg": {"beg", "begs", "begged", "begging"},
        "split": {"split", "splits", "splitting"},
        "hedge": {"hedge", "hedged", "hedges", "hedging"},
        "fall": {"fall", "falls", "fell", "fallen", "falling"},
        "hold": {"hold", "held", "holds", "holding"},
        "make": {"make", "made", "makes", "making"},
        "nip": {"nip", "nipped", "nips", "nipping"},
        "paint": {"paint", "painted", "paints", "painting"},
        "pull": {"pull", "pulled", "pulls", "pulling"},
        "put": {"put", "puts", "putting"},
        "run": {"run", "runs", "ran", "running"},
        "skim": {"skim", "skims", "skimmed", "skimming"},
        "speak": {"speak", "speaks", "spoke", "spoken", "speaking"},
        "stand": {"stand", "stands", "stood", "standing"},
        "weigh": {"weigh", "weighed", "weighs", "weighing"},
        "weather": {"weather", "weathered", "weathers", "weathering"},
    }
    core_words = [word for word in re.findall(r"[a-z']+", phrase.lower()) if word not in stop_words]
    if not core_words:
        return phrase.lower() in front.lower()
    hits = 0
    for word in core_words:
        accepted = variants.get(word, {word})
        if accepted & front_words:
            hits += 1
    required = min(len(core_words), 2)
    return hits >= required


def render_tsv(cards):
    with io.StringIO() as output:
        for line in ("#separator:tab", "#html:true"):
            output.write(f"{line}\n")
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(["SourceID", "Level", "Phrase", "Front", "FrontHTML", "Meaning", "Examples", "Tags"])
        for card in cards:
            writer.writerow(
                [
                    card["source_id"],
                    card["level"],
                    card["phrase"],
                    card["front"],
                    card["front_html"],
                    card["meaning"],
                    _html_list(card["examples"]),
                    card["tags"],
                ]
            )
        return output.getvalue()


def write_import_file(output_dir="generated/phrases"):
    cards = load_cards()
    errors = validate_cards(cards)
    if errors:
        preview = "\n".join(errors[:20])
        raise ValueError(f"Phrase card validation failed with {len(errors)} error(s):\n{preview}")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    path = output_path / "english_natural_phrases_import.tsv"
    path.write_text(render_tsv(cards), encoding="utf-8")
    return str(path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Generate English Natural Phrases Anki TSV.")
    parser.add_argument("--output-dir", default="generated/phrases")
    parser.add_argument("--summary", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    cards = load_cards()
    if args.summary:
        from collections import Counter

        counts = Counter(card["level"] for card in cards)
        for level in LEVELS:
            print(f"{level['id']}: {counts[level['id']]} cards")
        print(f"total: {len(cards)} cards")
        return 0
    path = write_import_file(args.output_dir)
    print(f"Wrote phrase import file: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
