import unittest
import csv
import io
from unittest.mock import patch, MagicMock
import os
import json
import re
import tempfile
from pathlib import Path
from collections import Counter, defaultdict

# Import functions from scripts if possible, or we can test the CLI behavior
# Since the scripts are mostly monolithic main blocks, we will test the key logic functions

import check_word
import get_pexels_image
import anki_tools
import grammar_levels
import spanish_grammar_levels
import spanish_core_learning
import spanish_deck
import sync_spanish_core_to_anki
import sync_4000_production_to_anki
import english_phrases
import english_mastery
import generate_english_turkish_cues


def _template_stem(text):
    cleaned = re.sub(r"\{\{c\d+::[^}]*\}\}", "", text)
    cleaned = cleaned.replace("_____", "")
    cleaned = re.sub(r"[\"'“”‘’]", "", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9 ]", " ", cleaned)
    words = [word.lower() for word in cleaned.split() if word]
    if len(words) < 3:
        return " ".join(words)
    return " ".join(words[:3])


class TestAnkiAutomation(unittest.TestCase):

    def test_check_word_load_vocabulary(self):
        """Test that the duplicate checker correctly identifies words from a mock file."""
        test_file = "test_deck.txt"
        with open(test_file, "w") as f:
            f.write("#separator:tab\n")
            f.write("guid1\tnotetype\tApple\tphonetic\tsound\tipa\n")
            f.write("guid2\tnotetype\t\"Banana\"\tphonetic\tsound\tipa\n")
        
        vocab = check_word.load_file_vocabulary(test_file)
        self.assertIn("apple", vocab)
        self.assertIn("banana", vocab)
        self.assertNotIn("cherry", vocab)
        os.remove(test_file)

    def test_grammar_cards_filtering(self):
        """Test grammar card filtering by level and card type."""
        cards = grammar_levels.get_cards(level="b2_tense_system")
        self.assertTrue(cards)
        self.assertTrue(all(card["level"] == "b2_tense_system" for card in cards))

        choose_cards = grammar_levels.get_cards(level="b2_tense_system", card_type="choose")
        self.assertTrue(choose_cards)
        self.assertTrue(all(card["card_type"] == "choose" for card in choose_cards))

        basic_cards = grammar_levels.get_cards(card_type="basic")
        self.assertTrue(all(card["card_type"] == "choose" for card in basic_cards))

    def test_grammar_level_minimum_counts(self):
        """Test the maintenance deck is compact, hard, and covers each level."""
        summary = {item["id"]: item["card_count"] for item in grammar_levels.get_level_summary()}
        total_cards = 0
        all_types = Counter()
        for level in grammar_levels.LEVELS:
            cards = grammar_levels.get_cards(level=level["id"])
            by_type = Counter(card["card_type"] for card in cards)

            self.assertGreaterEqual(len(cards), 12, f"Too few cards for {level['id']}.")
            self.assertEqual(set(by_type.keys()), {"choose"})
            self.assertGreaterEqual(by_type["choose"], 12)
            self.assertEqual(sum(by_type.values()), len(cards))
            self.assertEqual(summary[level["id"]], len(cards))
            all_types.update(by_type)
            total_cards += len(cards)

        self.assertGreaterEqual(total_cards, 90)
        self.assertLessEqual(total_cards, 140)
        self.assertEqual(set(all_types.keys()), {"choose"})
        self.assertGreater(all_types["choose"], 0)

    def test_grammar_tsv_renderers(self):
        """Test renderer boundaries for Basic and Cloze outputs."""
        cards = grammar_levels.get_cards()
        by_type = Counter(card["card_type"] for card in cards)
        basic_tsv = grammar_levels.render_basic_tsv(cards)
        cloze_tsv = grammar_levels.render_cloze_tsv(cards)

        self.assertIn("Topic\tLevel\tCardType\tFront\tAnswer\tReason\tExamples\tSelfGrade\tTags", basic_tsv)
        self.assertIn("Text\tExtra\tTags", cloze_tsv)
        self.assertNotIn("{{c1::", basic_tsv)
        self.assertNotIn("{{c1::", cloze_tsv)

        basic_reader = csv.reader(io.StringIO(basic_tsv), delimiter="\t")
        basic_rows = [row for row in basic_reader if row and not row[0].startswith("#")]
        cloze_reader = csv.reader(io.StringIO(cloze_tsv), delimiter="\t")
        cloze_rows = [row for row in cloze_reader if row and not row[0].startswith("#")]

        self.assertEqual(len(basic_rows), sum(by_type.values()) + 1)
        self.assertEqual(len(cloze_rows), 1)

    def test_grammar_formula_cards_exist(self):
        """Test explicit grammar formula cards for requested tense/modal/conditional systems."""
        choose_cards = grammar_levels.get_cards(card_type="choose")
        all_back_text = " | ".join(card["back"].lower() for card in choose_cards)
        expected_markers = [
            "have/has +",
            "had + v3",
            "will +",
            "going to +",
            "will have +",
            "be + v3",
            "modal",
            "modal + have + v3",
            "if + present, will + v1",
            "if + v2, would + v1",
            "if + had + v3, would have + v3",
            "a/an/the/zero",
            "who/which/that",
            "recommend/require + that",
            "nominalisation",
        ]
        for marker in expected_markers:
            self.assertIn(marker, all_back_text)

    def test_grammar_cards_no_known_bad_patterns(self):
        """Fail when legacy broken grammar templates are still present."""
        bad_patterns = [
            "sat {{c1::in}} the bench",
            "sat {{c1::under}} the bench",
            "sat {{c1::between}} the bench",
            "sat {{c1::with}} the bench",
            "sat {{c1::at}} the bench",
            "He drank {{c1::much}} piece of information during the presentation.",
            "He drank {{c1::some}} advice during the presentation.",
            "He drank {{c1::little}} homework during the presentation.",
            "He drank {{c1::some}} research during the presentation.",
            "You should {{c1::must}} complete the form today.",
            "You should {{c1::can}} complete the form today.",
            "You should {{c1::need to}} complete the form today.",
            "They always arrive {{c1::in}} the scheduled time.",
            "They always arrive {{c1::from}} the scheduled time.",
            "{{c1::Me}} and Me",
            "and my are in the meeting",
            "The files {{c1::was",
            "{{c1::we would}} we will",
            "Correct: he explained system yesterday",
            "{{c1::reading}} book",
            "It is {{c1::reading}}",
            "has passed}} QA yesterday",
            "received}} our meeting",
            "The person where",
            "The person when",
            "The person why",
            "The person which",
            "who {{c1::who explained}}",
            "where {{c1::where we met}}",
            "He prefers {{c1::to decide}} work",
            "He prefers {{c1::to imagine}}",
            "Please carry {{c1::on}} the problem",
            "the the problem",
            "Why sentence",
            "Whether sentence",
            "If sentence",
            "What I {{c1::really need}}.",
            "Do you {{c1::believe}}.",
            "The plan complete, and",
            "however}}, the final result improved",
            "{{c1::Therefore}} we delayed publication",
        ]
        card_text = []
        for card in grammar_levels.get_cards():
            for field in ("front", "text", "back"):
                value = card.get(field)
                if value:
                    card_text.append(value)
        all_text = "\n".join(card_text)
        for pattern in bad_patterns:
            self.assertNotIn(pattern, all_text, f"Found known bad grammar pattern: {pattern}")

    def test_grammar_passive_rule_examples(self):
        """Test passive voice is taught as a reusable choose card."""
        cards = [
            card
            for card in grammar_levels.get_cards(level="b2_sentence_control", card_type="choose")
            if card["topic"] == "passive voice"
        ]
        self.assertTrue(cards)
        text = "\n".join(card["back"].lower() for card in cards)
        for marker in ("be + v3", "was reviewed", "will be introduced", "had been"):
            self.assertIn(marker, text)

    def test_grammar_sentence_template_stem_repetition(self):
        """Fail if any exact template stem appears more than four times."""
        counts = Counter()
        for card in grammar_levels.get_cards():
            if card["card_type"] == "correction":
                continue
            template = card.get("front", "") or card.get("text", "")
            if "{{c1::" not in template and "_____" not in template:
                continue
            normalized = template.lower().strip()
            if re.match(r"^(choose|correct|complete|change|rewrite|use|change|an|it|she|he|they|we|i|you|the|this|that|these|those|if|when|where|what|how|why|wherever)", normalized):
                # Skip instruction-like prompts and short conversational starters
                continue
            stem = _template_stem(template)
            if not stem:
                continue
            counts[stem] += 1

        repeated = {stem: count for stem, count in counts.items() if count > 4}
        self.assertEqual(
            repeated,
            {},
            f"Template stems repeated too often: {sorted(repeated.items(), key=lambda item: item[1], reverse=True)}",
        )

    def test_no_cloze_guessing_cards(self):
        """Test this deck avoids low-value cloze guessing cards."""
        self.assertEqual(grammar_levels.get_cards(card_type="cloze"), [])
        all_text = "\n".join(
            str(card.get(field, ""))
            for card in grammar_levels.get_cards()
            for field in ("front", "text", "back")
        )
        low_value_patterns = [
            "I _____ a student",
            "In our archive",
            "The room contains",
            "Correct: am",
            "Correct: is",
            "Correct: are",
        ]
        for pattern in low_value_patterns:
            self.assertNotIn(pattern, all_text)

    def test_write_import_files(self):
        """Test grammar import file generation and headers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = grammar_levels.write_import_files(output_dir=tmpdir)
            basic_path = Path(paths[0])
            cloze_path = Path(paths[1])
            self.assertTrue(basic_path.exists())
            self.assertTrue(cloze_path.exists())

            cards = grammar_levels.get_cards()
            by_type = Counter(card["card_type"] for card in cards)

            basic = basic_path.read_text(encoding="utf-8")
            cloze = cloze_path.read_text(encoding="utf-8")
            self.assertIn("Topic\tLevel\tCardType\tFront\tAnswer\tReason\tExamples\tSelfGrade\tTags", basic)
            self.assertIn("Text\tExtra\tTags", cloze)

            basic_rows = [
                row
                for row in csv.reader(io.StringIO(basic), delimiter="\t")
                if row and not row[0].startswith("#")
            ]
            cloze_rows = [
                row
                for row in csv.reader(io.StringIO(cloze), delimiter="\t")
                if row and not row[0].startswith("#")
            ]

            self.assertEqual(len(basic_rows), sum(by_type.values()) + 1)
            self.assertEqual(len(cloze_rows), 1)

    def test_grammar_level_summary(self):
        """Test level summary structure and consistency with raw data."""
        summary = grammar_levels.get_level_summary()
        self.assertEqual(len(summary), len(grammar_levels.LEVELS))

        for item in summary:
            self.assertEqual(set(item.keys()), {"id", "name", "goal", "topics", "card_count"})
            self.assertIsInstance(item["id"], str)
            self.assertIsInstance(item["topics"], list)
            self.assertIsInstance(item["card_count"], int)
            self.assertGreater(item["card_count"], 0)
            actual_count = len([card for card in grammar_levels.GRAMMAR_CARDS if card["level"] == item["id"]])
            self.assertEqual(item["card_count"], actual_count)

    def test_spanish_grammar_a0_a2_structure(self):
        """Test Spanish grammar deck is level-based and cumulative for A0-A2."""
        level_ids = [level["id"] for level in spanish_grammar_levels.LEVELS]
        self.assertEqual(
            level_ids,
            ["a0_survival", "a1_1_foundations", "a1_2_core_sentences", "a2_1_daily_past", "a2_2_natural_spanish"],
        )

        cards = spanish_grammar_levels.get_cards()
        by_level = Counter(card["level"] for card in cards)
        by_type = Counter(card["card_type"] for card in cards)

        self.assertGreaterEqual(len(cards), 410)
        self.assertLessEqual(len(cards), 500)
        for level in level_ids:
            self.assertGreaterEqual(by_level[level], 60)
        for card_type in ("rule", "choose", "correction", "production", "pattern"):
            self.assertGreaterEqual(by_type[card_type], 82)

    def test_spanish_grammar_requested_topics_exist(self):
        """Test core A0-A2 Spanish grammar topics are represented."""
        topics = {card["topic"] for card in spanish_grammar_levels.get_cards()}
        expected_topics = {
            "noun gender",
            "adjective agreement",
            "ser basics",
            "ser vs estar",
            "regular -ar present",
            "hay",
            "tener and tener que",
            "ir a infinitive",
            "gustar basics",
            "reflexive verbs",
            "regular preterite",
            "preterite vs imperfect",
            "por vs para",
            "double object pronouns",
            "present perfect",
            "relative clauses and connectors",
            "numbers 0 to 20",
            "time basics",
            "ir present",
            "querer and poder present",
            "stem changing e to ie",
            "stem changing o to ue",
            "saber vs conocer",
            "personal a",
            "object pronoun placement",
            "negative words",
            "demonstratives",
            "regular imperfect forms",
            "preterite spelling changes",
            "negative commands",
            "basic subjunctive triggers",
            "impersonal se",
            "passive se",
            "conditional basics",
            "si clauses present future",
            "reported speech basics",
            "aunque indicative vs subjunctive recognition",
            "location prepositions",
            "muy vs mucho",
            "obligation variants",
            "quedar vs quedarse",
            "emotion verbs with prepositions",
        }
        self.assertTrue(expected_topics <= topics)

    def test_spanish_grammar_tsv_renderer(self):
        """Test Spanish grammar TSV renderer columns and row count."""
        cards = spanish_grammar_levels.get_cards()
        tsv = spanish_grammar_levels.render_tsv(cards)
        self.assertIn(
            "SourceID\tLevel\tTopic\tCardType\tCardTypeLabel\tFront\tAnswer\tExplanation\tExamples\tCommonMistake\tSelfGrade\tTags",
            tsv,
        )
        self.assertNotIn("{{c1::", tsv)

        rows = [
            row
            for row in csv.reader(io.StringIO(tsv), delimiter="\t")
            if row and not row[0].startswith("#")
        ]
        self.assertEqual(len(rows), len(cards) + 1)
        self.assertTrue(all(len(row) == 12 for row in rows))
        source_ids = [card["source_id"] for card in cards]
        self.assertEqual(len(source_ids), len(set(source_ids)))

    def test_spanish_grammar_no_known_bad_patterns(self):
        """Test Spanish grammar cards avoid impossible blanks and misleading forms."""
        all_text = "\n".join(
            str(card.get(field, ""))
            for card in spanish_grammar_levels.get_cards()
            for field in ("front", "answer", "explanation", "examples", "common_mistake")
        )
        bad_patterns = [
            "{{c1::",
            "____",
            "Write in Spanish: Write in Spanish:",
            "la problema\t",
            "Yo es profesor.\t",
            "Le lo doy.\t",
        ]
        for pattern in bad_patterns:
            self.assertNotIn(pattern, all_text)

    def test_spanish_core_learning_structure(self):
        """Test active Spanish core deck uses typed retrieval and sourced examples."""
        cards = spanish_core_learning.get_cards()
        by_level = Counter(card["Level"] for card in cards)
        by_type = Counter(card["CardType"] for card in cards)
        by_prompt = Counter(card["PromptMode"] for card in cards)

        self.assertGreaterEqual(len(cards), 900)
        self.assertLessEqual(len(cards), 1500)
        self.assertGreaterEqual(by_type["typed_correction"], 80)
        self.assertGreaterEqual(by_type["typed_production"], 80)
        self.assertGreaterEqual(by_type["typed_contrast"], 80)
        self.assertEqual(by_type["pattern"], 0)
        self.assertEqual(by_type["recognition"], 0)
        self.assertGreaterEqual(by_type["typed_cloze"], 350)
        self.assertGreaterEqual(by_type["audio_cloze"], 120)
        self.assertEqual(by_prompt["recognition"], 0)
        self.assertGreaterEqual(by_prompt["type_exact"] + by_prompt["type_compare"], 650)
        self.assertGreaterEqual(by_prompt["self_grade"], 250)
        self.assertGreaterEqual(by_level["b1_bridge"], 15)
        self.assertEqual(spanish_core_learning.validate_cards(cards), [])
        self.assertNotIn(
            "Meaning cue:",
            "\n".join(card["Front"] for card in cards),
        )

        typed_cards = [card for card in cards if card["PromptMode"].startswith("type_")]
        self.assertTrue(all(card["TypeAnswer"] == card["Answer"] for card in typed_cards))
        passive_cards = [card for card in cards if not card["PromptMode"].startswith("type_")]
        self.assertTrue(all(card["TypeAnswer"] == "" for card in passive_cards))

    def test_spanish_core_blanks_are_cued(self):
        """Test Spanish blank prompts include enough information to avoid pure guessing."""
        for card in spanish_core_learning.get_cards():
            front = card["Front"]
            if "_____" not in front:
                continue
            if card["CardType"] == "audio_cloze":
                self.assertIn("[sound:", front)
                continue
            self.assertTrue(
                any(marker in front for marker in ("front-cue", "Meaning:", "Contrast:")),
                f"{card['SourceID']} has an under-cued blank: {front}",
            )

        adjective = [
            card for card in spanish_core_learning.get_cards()
            if card["SourceID"] == "a0_survival::adjective_agreement::typed_contrast"
        ][0]
        self.assertIn("Contrast: rojo / roja", adjective["Front"])
        self.assertEqual("roja", adjective["Answer"])

        direct_object = [
            card for card in spanish_core_learning.get_cards()
            if card["SourceID"] == "a1_2_core_sentences::direct_object_pronouns::typed_contrast"
        ][0]
        self.assertIn("Contrast: Lo / La", direct_object["Front"])
        self.assertEqual("La", direct_object["Answer"])

        interleaved = [
            card for card in spanish_core_learning.get_cards()
            if card["SourceID"] == "interleaved::a1_1_foundations::ser_vs_estar_identity_vs_state::1"
        ][0]
        self.assertIn("Contrast: ser vs estar", interleaved["Front"])
        self.assertEqual("es | está", interleaved["Answer"])

    def test_spanish_open_ended_production_is_self_graded(self):
        """Test open-ended own-sentence production is not falsely exact-scored."""
        for card in spanish_core_learning.get_cards(card_type="typed_production"):
            if "type your own answer" in card["Front"].lower():
                self.assertEqual(card["PromptMode"], "self_grade")
                self.assertEqual(card["TypeAnswer"], "")

    def test_spanish_english_to_spanish_cards_do_not_repeat_answer_as_explanation(self):
        """Test sentence production cards avoid showing the same answer in every back section."""
        cards = [
            card
            for card in spanish_core_learning.get_cards(card_type="typed_production")
            if card["SourceID"].startswith("l1_l2::")
        ]
        self.assertTrue(cards)
        for card in cards:
            self.assertNotIn("L1→L2", card["Back"])
            self.assertNotIn("L1→L2", card["Formula"])
            self.assertNotEqual(card["Answer"], re.sub(r"<[^>]+>", "", card["Back"]).strip())
            self.assertFalse(re.sub(r"<[^>]+>", "", card["Back"]).strip().startswith(card["Answer"]))
            self.assertEqual("", card["Examples"])

    def test_spanish_core_no_known_bad_source_sentences(self):
        """Test known bad mined source text is corrected or rejected."""
        all_text = "\n".join(
            " ".join(str(card.get(field, "")) for field in ("Front", "Examples", "Back"))
            for card in spanish_core_learning.get_cards()
        )
        self.assertNotIn("A mi también", all_text)
        self.assertNotIn("¨¿Viste", all_text)

    def test_spanish_core_learning_tatoeba_attribution(self):
        """Test real sentence-mining cards keep stable Tatoeba source IDs."""
        cloze_cards = spanish_core_learning.get_cards(card_type="typed_cloze")
        self.assertGreaterEqual(len(cloze_cards), 350)
        for card in cloze_cards:
            self.assertIn("_____", card["Front"])
            self.assertIn("Tatoeba", card["Source"])
            self.assertIn("Source: Tatoeba.org sentence IDs", card["Attribution"])

        audio_cards = spanish_core_learning.get_cards(card_type="audio_cloze")
        self.assertGreaterEqual(len(audio_cards), 120)
        for card in audio_cards:
            self.assertIn("[sound:tatoeba_spa_", card["Front"])
            self.assertIn("_____", card["Front"])
            self.assertTrue(card["AudioURL"].startswith("https://audio.tatoeba.org/sentences/spa/"))
            self.assertTrue(card["Audio"].startswith("[sound:tatoeba_spa_"))
            self.assertTrue(card["AudioContributor"])
            self.assertTrue(card["AudioLicense"])

    def test_spanish_audio_dictation_source_ids_are_word_cloze(self):
        """Test former dictation cards ask for one heard word, not a whole sentence."""
        cards = [
            card for card in spanish_core_learning.get_cards()
            if card["SourceID"].startswith("tatoeba_dictation::")
        ]
        self.assertGreaterEqual(len(cards), 40)
        for card in cards:
            self.assertEqual(card["CardType"], "audio_cloze")
            self.assertEqual(card["PromptMode"], "type_exact")
            self.assertIn("[sound:tatoeba_spa_", card["Front"])
            self.assertIn("_____", card["Front"])
            self.assertNotIn("Type the full Spanish sentence", card["Front"])
            self.assertNotIn("Full dictation", card["Formula"])
            self.assertNotRegex(card["Answer"], r"\s")

    def test_spanish_tatoeba_sentence_roles_do_not_overlap(self):
        """Test one source sentence is not reused across text, audio, and dictation modes."""
        sentence_roles = defaultdict(set)
        for card in spanish_core_learning.get_cards():
            source_id = card["SourceID"]
            if source_id.startswith("tatoeba::"):
                parts = source_id.split("::")
                sentence_roles[parts[2]].add(card["CardType"])
            elif source_id.startswith("tatoeba_audio::"):
                parts = source_id.split("::")
                sentence_roles[parts[2]].add(card["CardType"])
            elif source_id.startswith("tatoeba_dictation::"):
                parts = source_id.split("::")
                sentence_roles[parts[2]].add(card["CardType"])

        overlaps = {
            sentence_id: roles
            for sentence_id, roles in sentence_roles.items()
            if len(roles) > 1
        }
        self.assertEqual(overlaps, {})

    def test_spanish_pronunciation_hint_examples(self):
        """Test readable Latin American Spanish pronunciation hints."""
        examples = {
            "año": "A-nyo",
            "mochila": "mo-ÇI-la",
            "cinturón": "sin-tu-RON",
            "queso": "KE-so",
            "guitarra": "gi-TAR-ra",
            "llave": "YA-be",
            "jardín": "har-DIN",
            "círculo": "SIR-ku-lo",
            "el cinturón": "el sin-tu-RON",
        }
        for word, expected in examples.items():
            self.assertEqual(spanish_deck.spanish_pronunciation_hint(word), expected)
            self.assertNotIn("İ", spanish_deck.spanish_pronunciation_hint(word))

    def test_spanish_metadata_uses_conservative_forms(self):
        """Test inferred Spanish grammar does not invent risky forms."""
        noun = spanish_deck.infer_spanish_metadata("el cinturón")
        self.assertEqual(noun["spanish_forms"], "singular: el cinturón; plural: los cinturones")

        verb = spanish_deck.infer_spanish_metadata("aprobar")
        self.assertIn("-ar pattern", verb["spanish_forms"])
        self.assertIn("check irregular or stem-changing forms separately", verb["spanish_forms"])
        self.assertNotIn("aprobo", verb["spanish_forms"])

    def test_spanish_glossary_has_complete_mirror_fields_and_sense_notes(self):
        """Test durable Spanish glossary keeps English mirrors and duplicate-sense notes."""
        glossary_path = Path("generated/spanish_reviewed_glossary_full.tsv")
        with glossary_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))

        self.assertEqual(sum(1 for row in rows if not row["spanish_meaning_en"]), 0)
        self.assertEqual(sum(1 for row in rows if not row["spanish_example_en"]), 0)

        notes_by_pair = {(row["english"], row["spanish"]): row["notes"] for row in rows}
        self.assertIn("color", notes_by_pair[("navy", "azul marino")])
        self.assertIn("military", notes_by_pair[("navy", "armada")])
        self.assertIn("lower part", notes_by_pair[("bottom", "la parte inferior")])
        self.assertIn("lowest point", notes_by_pair[("bottom", "fondo")])

    def test_spanish_examples_track_source_examples_for_known_rows(self):
        """Test source-backed rows do not use unrelated Spanish example sentences."""
        glossary_path = Path("generated/spanish_reviewed_glossary_full.tsv")
        with glossary_path.open(encoding="utf-8", newline="") as handle:
            rows = {row["english"]: row for row in csv.DictReader(handle, delimiter="\t")}

        expected_examples = {
            "agree": "Los estudiantes están de acuerdo en que tienen demasiados deberes.",
            "alcohol": "Una persona no debe conducir un coche después de haber bebido alcohol.",
            "arrive": "Llegaron a la escuela a las 7 a.m.",
            "catch": "¿Atrapaste la pelota durante el partido de béisbol?",
            "apart": "Se separaron y luego volvieron a juntarse.",
            "attribute": "Él no es muy inteligente, pero sí tiene otros atributos positivos.",
            "bilingual": "Como ya sabes inglés, después de aprender francés serás bilingüe.",
            "completely": "Estaba completamente equivocado.",
            "dash": "Helen corrió por las escaleras para que no llegara tarde a su cita.",
            "plate": "Puse mi plato sobre la mesa para poder ponerle comida.",
            "arena": "El nuevo estadio estaba listo para albergar el partido por el campeonato.",
            "depot": "Esperó a que su madre llegara a la estación.",
            "acceptance": "Mostré mi aceptación de la solución propuesta.",
            "launch": "El barco zarpó del muelle y flotó río abajo.",
            "ice skating": "Me gusta patinar sobre hielo.",
        }
        for english, expected in expected_examples.items():
            self.assertEqual(rows[english]["spanish_example"], expected)
        self.assertEqual(rows["plate"]["spanish"], "el plato")
        self.assertEqual(rows["plate"]["spanish_meaning"], "Un plato es un objeto plano y redondo en el que pones comida.")
        self.assertEqual(rows["arena"]["spanish"], "el estadio")
        self.assertEqual(rows["depot"]["spanish"], "la estación")
        self.assertEqual(rows["ice skating"]["english"], "ice skating")
        self.assertEqual(rows["acceptance"]["english_example"], "I showed my acceptance of the proposed solution.")
        self.assertEqual(rows["launch"]["english_example"], "The boat launched from the dock and floated down the river.")
        self.assertNotIn("<", rows["agree"]["english_meaning"])
        self.assertNotIn("<", rows["agree"]["english_example"])

    def test_english_phrase_deck_quality(self):
        """Test the natural phrase deck has concrete phrase-recognition cards."""
        cards = english_phrases.load_cards()
        by_level = Counter(card["level"] for card in cards)

        self.assertGreaterEqual(len(cards), 250)
        self.assertLessEqual(len(cards), 500)
        for level in english_phrases.LEVELS:
            self.assertGreaterEqual(by_level[level["id"]], 45)

        errors = english_phrases.validate_cards(cards)
        self.assertEqual(errors, [])

    def test_english_phrase_tsv_renderer(self):
        """Test phrase deck import TSV structure."""
        cards = english_phrases.load_cards()
        rendered = english_phrases.render_tsv(cards)
        self.assertIn("SourceID\tLevel\tPhrase\tFront\tFrontHTML\tMeaning\tExamples\tTags", rendered)
        rows = [
            row
            for row in csv.reader(io.StringIO(rendered), delimiter="\t")
            if row and not row[0].startswith("#")
        ]
        self.assertEqual(len(rows), len(cards) + 1)
        self.assertTrue(all(len(row) == 8 for row in rows))
        self.assertIn('<span class="target-phrase">good morning</span>', rows[1][4])
        self.assertEqual(len({card["source_id"] for card in cards}), len(cards))
        self.assertIn("Good morning, everyone; let's start with the updates.", rendered)
        self.assertNotIn("Good morning, everyone<br>- let's start", rendered)

    def test_english_phrase_deck_no_known_bad_examples(self):
        """Fail on known unnatural phrase examples."""
        all_text = "\n".join(
            " ".join(str(card.get(field, "")) for field in ("phrase", "front", "meaning", "examples"))
            for card in english_phrases.load_cards()
        ).lower()
        bad_patterns = [
            "asked me to call me",
            "get on here",
            "take in your bags",
            "cannot in no way",
            "filled in full",
            "sold out in full",
            "went in full swing",
            "whenever your data is in your best interest",
        ]
        for pattern in bad_patterns:
            self.assertNotIn(pattern, all_text)

    def test_english_mastery_structure(self):
        """Test English Mastery uses active recall instead of recognition decks."""
        cards = english_mastery.get_cards()
        by_type = Counter(card["CardType"] for card in cards)
        by_prompt = Counter(card["PromptMode"] for card in cards)

        self.assertGreaterEqual(len(cards), 950)
        self.assertLessEqual(len(cards), 1200)
        self.assertGreaterEqual(by_type["phrase_cloze"], 350)
        self.assertGreaterEqual(by_type["phrase_production"], 250)
        self.assertGreaterEqual(by_type["typed_contrast"], 90)
        self.assertGreaterEqual(by_type["typed_cloze"], 100)
        self.assertGreaterEqual(by_type["audio_cloze"], 100)
        self.assertGreaterEqual(by_type["dictation"], 50)
        self.assertEqual(by_type["recognition"], 0)
        self.assertEqual(by_prompt["recognition"], 0)
        self.assertGreaterEqual(by_prompt["type_exact"] + by_prompt["type_compare"], 550)
        self.assertGreaterEqual(by_prompt["self_grade"], 300)
        self.assertEqual(english_mastery.validate_cards(cards), [])

    def test_english_mastery_phrase_context_quality(self):
        """Test phrase cloze cards include context and do not leak the answer."""
        for card in english_mastery.get_cards(card_type="phrase_cloze"):
            self.assertIn("Meaning cue", card["Front"])
            self.assertIn("Complete naturally", card["Front"])
            self.assertIn("_____", card["Front"])
            self.assertNotIn("A)", card["Front"])
            self.assertNotIn("B)", card["Front"])
            front_without_blank = card["Front"].lower().replace("_____", "")
            self.assertNotIn(card["Answer"].lower(), front_without_blank)

    def test_english_open_ended_production_is_self_graded(self):
        """Test open-ended production is active recall, not false exact-answer typing."""
        for card in english_mastery.get_cards(card_type="phrase_production"):
            self.assertEqual(card["PromptMode"], "self_grade")
            self.assertEqual(card["TypeAnswer"], "")

    def test_english_mastery_back_fields_are_not_redundant(self):
        """Test English Mastery back fields do not repeat answers as fake explanations."""
        def clean(text):
            text = re.sub(r"<br\s*/?>", "\n", text or "")
            text = re.sub(r"<[^>]+>", "", text)
            text = re.sub(r"&[#A-Za-z0-9]+;", " ", text)
            return re.sub(r"\s+", " ", text).strip().strip("-").strip()

        issues = []
        for card in english_mastery.get_cards():
            answer = clean(card["Answer"])
            back = clean(card["Back"])
            examples = clean(card["Examples"])
            if card["CardType"] == "phrase_cloze" and back.lower().startswith(answer.lower() + " ="):
                issues.append((card["SourceID"], "phrase meaning repeats answer"))
            if card["CardType"] == "interleaved_contrast" and answer:
                answer_parts = [part.strip() for part in answer.split("|")]
                if any(part and part in back for part in answer_parts):
                    issues.append((card["SourceID"], "interleaved why repeats answer"))
                if examples:
                    issues.append((card["SourceID"], "interleaved examples repeat answer"))
            if card["CardType"] == "dictation" and examples == answer:
                issues.append((card["SourceID"], "dictation examples equal answer"))

        self.assertEqual([], issues[:20])

    def test_english_tatoeba_sentence_roles_do_not_overlap(self):
        """Test one English source sentence is not reused across text and audio modes."""
        sentence_roles = defaultdict(set)
        for card in english_mastery.get_cards():
            source_id = card["SourceID"]
            if source_id.startswith("tatoeba_eng_mining::"):
                sentence_roles[source_id.split("::")[2]].add(card["CardType"])
            elif source_id.startswith("tatoeba_eng_audio::"):
                sentence_roles[source_id.split("::")[1]].add(card["CardType"])
            elif source_id.startswith("tatoeba_eng_dictation::"):
                sentence_roles[source_id.split("::")[1]].add(card["CardType"])

        overlaps = {
            sentence_id: roles
            for sentence_id, roles in sentence_roles.items()
            if len(roles) > 1
        }
        self.assertEqual(overlaps, {})

    def test_english_grammar_back_does_not_duplicate_examples(self):
        """Test grammar examples render only in the dedicated Examples field."""
        grammar_cards = [
            card for card in english_mastery.get_cards()
            if card["SourceID"].startswith(("grammar::", "grammar_rule::"))
        ]
        self.assertTrue(grammar_cards)
        for card in grammar_cards:
            self.assertNotIn("Examples-", card["Back"])
            self.assertNotIn("<b>Examples</b>", card["Back"])
            self.assertNotIn("Self-Grade", card["Back"])
            self.assertIn("Good =", card["SelfGrade"])
            if card["Examples"]:
                self.assertTrue(card["Examples"].startswith("- "))

    def test_english_mastery_audio_sources(self):
        """Test listening cards keep source and media metadata."""
        audio_cards = [card for card in english_mastery.get_cards() if card["AudioURL"]]
        self.assertGreaterEqual(len(audio_cards), 160)
        for card in audio_cards:
            self.assertTrue(card["Audio"].startswith("[sound:tatoeba_eng_"))
            self.assertTrue(card["AudioURL"].startswith("https://audio.tatoeba.org/sentences/eng/"))
            self.assertIn("Tatoeba", card["Source"])
            self.assertIn("Tatoeba.org English sentence ID", card["Attribution"])

    def test_english_contrast_single_blank_consistent(self):
        """Test typed_contrast cards have exactly one blank of consistent width."""
        contrast_cards = english_mastery.get_cards(card_type="typed_contrast")
        self.assertGreaterEqual(len(contrast_cards), 90)
        for card in contrast_cards:
            front = card["Front"]
            blanks = re.findall(r"_{4,}", front)
            self.assertEqual(len(blanks), 1, f"Expected 1 blank, found {len(blanks)} in: {front[:100]}")
            self.assertEqual(blanks[0], "_____", f"Inconsistent blank width '{blanks[0]}' in: {front[:100]}")
            self.assertNotIn("Choose:", front)
            self.assertNotIn("A)", front)
            self.assertNotIn("B)", front)

    def test_english_contrast_front_answer_consistency(self):
        """Test typed_contrast answer aligns with front (text before/after blank must match, ignoring trailing punctuation)."""
        contrast_cards = english_mastery.get_cards(card_type="typed_contrast")
        for card in contrast_cards:
            front = re.sub(r"<br><br><span class=\"front-cue\">.*$", "", card["Front"])
            front = re.sub(r"<[^>]+>", "", front)
            front = re.sub(r"(?i)^type the correct/natural english form\s*", "", front).strip()
            answer = card["Answer"]
            parts = re.split(r"_{3,}", front, maxsplit=1)
            if len(parts) != 2:
                self.fail(f"No blank found in front: {front[:100]}")
            before = parts[0].strip().lower().rstrip(".")
            after = parts[1].strip().lower().rstrip(".")
            ans = answer.strip().lower().rstrip(".")
            if before and not ans.startswith(before):
                self.fail(
                    f"Answer does not start with front text before blank.\n"
                    f"  Expected start: '{before[:60]}'\n"
                    f"  Answer: '{ans[:100]}'"
                )
            if after and not ans.endswith(after):
                self.fail(
                    f"Answer does not end with front text after blank.\n"
                    f"  Expected end: '{after[:60]}'\n"
                    f"  Answer: '{ans[:100]}'"
                )

    def test_english_contrast_lexical_cues_when_needed(self):
        """Test semantically ambiguous grammar cloze cards include lexical target cues."""
        contrast_cards = english_mastery.get_cards(card_type="typed_contrast")
        reviewed = [
            card for card in contrast_cards
            if "We _____ three versions already this week" in card["Front"]
        ]
        self.assertEqual(len(reviewed), 1)
        self.assertIn("Target cue", reviewed[0]["Front"])
        self.assertIn("review", reviewed[0]["Front"])
        london = [
            card for card in contrast_cards
            if "I _____ in London since 2018" in card["Front"]
        ]
        self.assertEqual(len(london), 1)
        self.assertIn("Target cue", london[0]["Front"])
        self.assertIn("live", london[0]["Front"])
        self.assertNotIn("i / live", london[0]["Front"].lower())

    def test_no_trailing_periods_except_dictation(self):
        """Test no trailing periods in Answer/TypeAnswer except for dictation cards."""
        for card in spanish_core_learning.get_cards():
            self.assertNotRegex(card["Answer"], r"\.+$",
                f"Spanish card has trailing period: [{card['SourceID']}] {card['Answer'][:60]}")
        for card in english_mastery.get_cards():
            if card["CardType"] == "dictation":
                continue
            self.assertNotRegex(card["Answer"], r"\.+$",
                f"English card has trailing period: [{card['SourceID']}] {card['Answer'][:60]}")

    def test_english_audio_cloze_target_variety(self):
        """Test audio_cloze has enough target variety (>= 30 unique targets)."""
        audio_cards = english_mastery.get_cards(card_type="audio_cloze")
        targets = [card["Answer"] for card in audio_cards]
        unique = set(targets)
        self.assertGreaterEqual(len(unique), 30,
            f"Only {len(unique)} unique audio_cloze targets; expected >= 30")
        from collections import Counter
        counts = Counter(targets)
        for target, count in counts.items():
            self.assertLessEqual(count, 4,
                f"Audio target '{target}' has {count} cards; expected <= 4")

    def test_english_sentence_mining_cards(self):
        """Test typed_cloze sentence mining cards from Tatoeba."""
        mining_cards = english_mastery.get_cards(card_type="typed_cloze")
        self.assertGreaterEqual(len(mining_cards), 100)
        for card in mining_cards:
            self.assertIn("_____", card["Front"])
            self.assertIn("Complete the English from context", card["Front"])
            self.assertIn("Target cue", card["Front"])
            self.assertIn("Tatoeba", card["Source"])
            self.assertNotIn("Choose:", card["Front"])
            front_without_blank = card["Front"].lower().replace("_____", "")
            self.assertNotIn(card["Answer"].lower(), front_without_blank)

    def test_spanish_parser_extracts_rows(self):
        """Test TSV parser fields for the new Spanish duplicate workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.tsv"
            source_path.write_text(
                "#separator:tab\n"
                "#guid column:1\n"
                "#notetype column:2\n"
                "#deck column:3\n"
                "#card number column:4\n"
                "#image column:5\n"
                "#word column:6\n"
                "#phonetic column:7\n"
                "#sound column:8\n"
                "#ipa column:9\n"
                "g1\t4000 EEW Extra\t4000 Essential English Words::Extra\t2_1\t<img/>\tapple\t[æpəl]\t[sound:apple.mp3]\t[æpəl]\n"
                "g2\t4000 EEW Extra\t4000 Essential English Words::Extra\t2_2\t<img/>\tbanana\t[ˈbænənə]\t[sound:banana.mp3]\t[ˈbænənə]\n",
                encoding="utf-8",
            )

            rows = spanish_deck.parse_source_deck(str(source_path))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["guid"], "g1")
            self.assertEqual(rows[0]["english_word"], "apple")
            self.assertEqual(rows[0]["card_number"], "2_1")
            self.assertEqual(rows[0]["ipa"], "[æpəl]")

    def test_spanish_parser_handles_known_mixed_4000_formats(self):
        """Test parser does not treat sound fields as words in main 4000 EEW rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.tsv"
            source_path.write_text(
                "#separator:tab\n"
                "g1\t4000 EEW\t4000 Essential English Words::1.Book\tagree\t<img src=\"01.jpg\">\t"
                "[sound:agree.mp3]\t[sound:meaning.mp3]\t[sound:example.mp3]\t"
                "To agree is to have the same opinion.\tThe students agree.\təˈɡriː\t\n"
                "g2\t4000 EEW Extra\t4000 Essential English Words::Extra\t2_1\t<img/>\tbackpack\t"
                "['bækpæk]\t[sound:backpack.mp3]\t[ˈbækpæk]\t[ˈbækpæk]\t[ˈbækpæk]\t\n",
                encoding="utf-8",
            )

            rows = spanish_deck.parse_source_deck(str(source_path))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["english_word"], "agree")
            self.assertEqual(rows[0]["sound"], "[sound:agree.mp3]")
            self.assertEqual(rows[0]["english_meaning"], "To agree is to have the same opinion.")
            self.assertEqual(rows[0]["english_example"], "The students agree.")
            self.assertEqual(rows[1]["english_word"], "backpack")
            self.assertEqual(rows[1]["english_meaning"], "")
            self.assertEqual(rows[1]["english_example"], "")
            self.assertEqual(rows[1]["card_number"], "2_1")

    def test_spanish_parser_does_not_invent_extra_meaning_and_example(self):
        """Test parser does not treat Extra IPA columns as meaning/example text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.tsv"
            source_path.write_text(
                "#separator:tab\n"
                "g1\t4000 EEW Extra\t4000 Essential English Words::Extra\t2_1\t<img/>\tbackpack\t"
                "[bækpæk]\t[sound:backpack.mp3]\t[bækpæk]\tA bag carried on the back.\tShe carried a backpack.\t\n",
                encoding="utf-8",
            )

            rows = spanish_deck.parse_source_deck(str(source_path))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["english_word"], "backpack")
            self.assertEqual(rows[0]["english_meaning"], "")
            self.assertEqual(rows[0]["english_example"], "")

    def test_spanish_parser_keeps_guid_that_starts_with_hash(self):
        """Test Anki GUIDs starting with # are not mistaken for header lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.tsv"
            source_path.write_text(
                "#separator:tab\n"
                "#abc\t4000 EEW\t4000 Essential English Words::3.Book\tpenny\t<img/>\t"
                "[sound:penny.mp3]\t[sound:meaning.mp3]\t[sound:example.mp3]\t"
                "A penny is a coin.\tThe penny is small.\tˈpeni\t\n",
                encoding="utf-8",
            )

            rows = spanish_deck.parse_source_deck(str(source_path))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["guid"], "#abc")
            self.assertEqual(rows[0]["english_word"], "penny")

    def test_glossary_matching_marks_reviewed_vs_pending(self):
        """Test reviewed and needs_translation statuses from glossary matches."""
        source_rows = [
            {"english_word": "apple", "deck": "4000 Essential English Words::Extra", "card_number": "2_1"},
            {"english_word": "banana", "deck": "4000 Essential English Words::Extra", "card_number": "2_2"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_path = Path(tmpdir) / "glossary.csv"
            glossary_path.write_text(
                "english,spanish,spanish_example,notes\n"
                "apple,manzana,\"La manzana es roja.\",fruit\n",
                encoding="utf-8",
            )

            glossary = spanish_deck.load_glossary(str(glossary_path))
            rows = spanish_deck.build_spanish_rows(source_rows, glossary)
            self.assertEqual(rows[0]["status"], spanish_deck.STATUS_REVIEWED)
            self.assertEqual(rows[0]["spanish"], "manzana")
            self.assertEqual(rows[1]["status"], spanish_deck.STATUS_NEEDS_TRANSLATION)
            self.assertEqual(rows[1]["spanish"], "")

    def test_spanish_glossary_supports_spanish_meaning(self):
        """Test glossary can provide translated meanings with spanish_meaning header."""
        source_rows = [
            {"english_word": "apple", "deck": "4000 Essential English Words::Extra", "card_number": "2_1"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_path = Path(tmpdir) / "glossary.tsv"
            glossary_path.write_text(
                "english\tspanish\tspanish_meaning\tspanish_example\tnotes\n"
                "apple\tmanzana\tfruta\tLa manzana es roja.\tfruit\n",
                encoding="utf-8",
            )

            glossary = spanish_deck.load_glossary(str(glossary_path))
            rows = spanish_deck.build_spanish_rows(source_rows, glossary)
            self.assertEqual(rows[0]["spanish_meaning"], "fruta")

    def test_spanish_clear_nouns_get_articles(self):
        """Test clear noun-definition rows display the article for learning gender."""
        source_rows = [
            {
                "english_word": "boat",
                "english_meaning": "A boat is a vehicle that moves across water.",
                "english_example": "The boat moved quickly.",
                "deck": "4000 Essential English Words::1.Book",
                "card_number": "",
            },
            {
                "english_word": "arrive",
                "english_meaning": "To arrive is to get somewhere.",
                "english_example": "They arrive late.",
                "deck": "4000 Essential English Words::1.Book",
                "card_number": "",
            },
            {
                "english_word": "August",
                "english_meaning": "August is the eighth month of the year.",
                "english_example": "August is hot.",
                "deck": "4000 Essential English Words::1.Book",
                "card_number": "",
            },
        ]
        glossary = {
            "boat": {"spanish": "barco", "english": "boat"},
            "arrive": {"spanish": "llegar", "english": "arrive"},
            "august": {"spanish": "agosto", "english": "August"},
        }
        rows = spanish_deck.build_spanish_rows(source_rows, glossary)
        self.assertEqual(rows[0]["spanish"], "el barco")
        self.assertEqual(rows[0]["spanish_article"], "el")
        self.assertEqual(rows[0]["spanish_part_of_speech"], "noun")
        self.assertEqual(rows[1]["spanish"], "llegar")
        self.assertEqual(rows[1]["spanish_part_of_speech"], "verb")
        self.assertEqual(rows[2]["spanish"], "agosto")

    def test_spanish_noun_metadata_handles_article_exceptions(self):
        """Test feminine nouns with non-obvious articles keep correct gender/forms."""
        source_rows = [
            {
                "english_word": "water",
                "english_meaning": "Water is a clear liquid that people need.",
                "english_example": "Drink water.",
                "deck": "4000 Essential English Words::1.Book",
                "card_number": "",
            },
            {
                "english_word": "cathedral",
                "english_meaning": "A cathedral is an important church.",
                "english_example": "The cathedral is large.",
                "deck": "4000 Essential English Words::1.Book",
                "card_number": "",
            },
            {
                "english_word": "flame",
                "english_meaning": "A flame is part of a fire.",
                "english_example": "The flame is bright.",
                "deck": "4000 Essential English Words::1.Book",
                "card_number": "",
            },
            {
                "english_word": "football",
                "english_meaning": "Football is a sport with an oval ball.",
                "english_example": "Football is popular in the United States.",
                "deck": "4000 Essential English Words::1.Book",
                "card_number": "",
            },
        ]
        glossary = {
            "water": {"spanish": "agua", "english": "water"},
            "cathedral": {"spanish": "catedral", "english": "cathedral"},
            "flame": {"spanish": "llama", "english": "flame"},
            "football": {"spanish": "fútbol americano", "english": "football"},
        }
        rows = spanish_deck.build_spanish_rows(source_rows, glossary)
        self.assertEqual(rows[0]["spanish"], "el agua")
        self.assertEqual(rows[0]["spanish_gender"], "feminine")
        self.assertIn("plural: las aguas", rows[0]["spanish_forms"])
        self.assertEqual(rows[1]["spanish"], "la catedral")
        self.assertEqual(rows[1]["spanish_gender"], "feminine")
        self.assertEqual(rows[2]["spanish"], "la llama")
        self.assertEqual(rows[2]["spanish_gender"], "feminine")
        self.assertEqual(rows[3]["spanish"], "el fútbol americano")
        self.assertIn("plural: los fútboles americanos", rows[3]["spanish_forms"])

    def test_spanish_glossary_disambiguates_duplicate_words_by_context(self):
        """Test duplicate English words can keep different Spanish senses."""
        source_rows = [
            {
                "english_word": "navy",
                "english_meaning": "",
                "english_example": "",
                "deck": "4000 Essential English Words::Extra",
                "card_number": "1_1_75",
            },
            {
                "english_word": "navy",
                "english_meaning": "A navy is the part of a country's military that fights at sea.",
                "english_example": "My country is known for our strong navy.",
                "deck": "4000 Essential English Words::3.Book",
                "card_number": "",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_path = Path(tmpdir) / "glossary.tsv"
            glossary_path.write_text(
                "english\tenglish_meaning\tenglish_example\tspanish\tspanish_meaning\tspanish_example\tnotes\n"
                "navy\t\t\tazul marino\tColor azul oscuro.\tEl abrigo es azul marino.\t\n"
                "navy\tA navy is the part of a country's military that fights at sea.\t"
                "My country is known for our strong navy.\t"
                "armada\tFuerza militar que combate por mar.\tMi país tiene una armada fuerte.\t\n",
                encoding="utf-8",
            )

            glossary = spanish_deck.load_glossary(str(glossary_path))
            rows = spanish_deck.build_spanish_rows(source_rows, glossary)
            self.assertEqual(rows[0]["spanish"], "azul marino")
            self.assertEqual(rows[1]["spanish"], "la armada")

    def test_output_generation_respects_limit(self):
        """Test output generators do not exceed the requested limit."""
        source_rows = [
            {"english_word": f"word{i}", "deck": "4000 Essential English Words::Extra", "card_number": f"2_{i}"}
            for i in range(10)
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path, basic_path = spanish_deck.write_spanish_files(
                source_rows,
                {},
                output_dir=tmpdir,
                limit=3,
            )
            self.assertTrue(Path(review_path).exists())
            self.assertTrue(Path(basic_path).exists())

            with open(review_path, encoding="utf-8", newline="") as handle:
                review_rows = list(csv.reader(handle, delimiter="\t"))
            with open(basic_path, encoding="utf-8", newline="") as handle:
                basic_rows = list(csv.reader(handle, delimiter="\t"))
            review_data = [row for row in review_rows if row and not row[0].startswith("#")]
            basic_data = [row for row in basic_rows if row and not row[0].startswith("#")]
            self.assertEqual(
                review_data[0],
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
            )
            self.assertEqual(len(review_data) - 1, 3)
            self.assertEqual(len(basic_data) - 1, 3)

    def test_basic_import_tsv_uses_spanish_recognition_format(self):
        """Test reviewed basic cards put Spanish on front and English/context on back."""
        source_rows = [
            {
                "english_word": "apple",
                "english_meaning": "An apple is a fruit.",
                "english_example": "The apple is red.",
                "image": '<img src="apple.jpg" />',
                "deck": "4000 Essential English Words::Extra",
                "card_number": "2_1",
            }
        ]
        glossary = {
            "apple": {
                "spanish": "manzana",
                "spanish_meaning": "fruta",
                "spanish_example": "La manzana es roja.",
                "notes": "fruit",
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            _, basic_path = spanish_deck.write_spanish_files(source_rows, glossary, output_dir=tmpdir)
            with open(basic_path, encoding="utf-8", newline="") as handle:
                basic_rows = list(csv.reader(handle, delimiter="\t"))
            basic_data = [row for row in basic_rows if row and not row[0].startswith("#")]
            self.assertEqual(len(basic_data), 2)
            self.assertEqual(basic_data[1][0], '<img src="apple.jpg" />\nla manzana\nla man-SA-na')
            back = basic_data[1][1]
            self.assertIn("English: apple", back)
            self.assertIn("Pronunciation: la man-SA-na", back)
            self.assertIn("Spanish meaning: fruta", back)
            self.assertIn("Meaning in English: An apple is a fruit.", back)
            self.assertIn("Spanish example: La manzana es roja.", back)
            self.assertIn("Example in English: The apple is red.", back)
            self.assertNotIn("Part of speech: adjective", back)
            self.assertNotIn("English source:", back)
            self.assertIn("Notes: fruit", back)

    def test_no_translation_invented_without_glossary(self):
        """Test no Spanish translation is produced when glossary is absent."""
        source_rows = [
            {"english_word": "unverified", "deck": "4000 Essential English Words::Extra", "card_number": "3_1"}
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            rows = spanish_deck.build_spanish_rows(source_rows, {})
            self.assertEqual(rows[0]["status"], spanish_deck.STATUS_NEEDS_TRANSLATION)
            self.assertEqual(rows[0]["spanish"], "")

            _, basic_path = spanish_deck.write_spanish_files(source_rows, {}, output_dir=tmpdir)
            with open(basic_path, encoding="utf-8", newline="") as handle:
                basic_rows = list(csv.reader(handle, delimiter="\t"))
            basic_data = [row for row in basic_rows if row and not row[0].startswith("#")]
            self.assertEqual(len(basic_data), 2)
            self.assertIn("TODO", basic_data[1][1])
            review_path = Path(tmpdir) / "english_spanish_review.tsv"
            self.assertTrue(review_path.exists())
            with open(review_path, encoding="utf-8", newline="") as handle:
                review_rows = list(csv.reader(handle, delimiter="\t"))
            review_data = [row for row in review_rows if row and not row[0].startswith("#")]
            self.assertEqual(len(review_data), 2)
            self.assertEqual(review_data[1][0], "unverified")
            self.assertEqual(review_data[1][3], "")
            self.assertEqual(review_data[1][4], "")
            self.assertEqual(review_data[1][5], "")
            self.assertEqual(review_data[1][6], "")

    def test_spanish_reviewed_glossary_has_no_known_bad_translation_artifacts(self):
        """Fail on known OCR/profanity/accent artifacts that reached reviewed Spanish rows."""
        paths = [
            Path("generated/spanish_reviewed_glossary_full.tsv"),
            Path("generated/spanish_full/english_spanish_review.tsv"),
        ]
        bad_patterns = [
            "maricón",
            "ell poema",
            "Aplausar es",
            "está moda",
            "Russian fag",
            "gordo y al nivel",
            "\tofensa\t",
            "\toffender\t",
            "el víctima",
            "los víctimas",
            "inquietud o inquietud",
            "picar y picar",
            "camino o camino",
            "debajo o debajo",
            "brillar y brillar",
            "avergonzado y avergonzado",
            " accion ",
            " carcel ",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for pattern in bad_patterns:
                self.assertNotIn(pattern, text, f"{path} contains known bad artifact: {pattern}")

    def test_spanish_marked_sense_fixes_stay_aligned(self):
        """Test marked Spanish 4000 rows teach the example sense consistently."""
        path = Path("generated/spanish_full/english_spanish_review.tsv")
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                row["English"]: row
                for row in csv.DictReader((line for line in handle if not line.startswith("#")), delimiter="\t")
            }

        shake = rows["shake"]
        self.assertEqual(shake["Spanish"], "dar la mano")
        self.assertIn("shake hands", shake["English Meaning"])
        self.assertIn("da la mano", shake["Spanish Example"])

        spread = rows["spread"]
        self.assertEqual(spread["Spanish"], "untar")
        self.assertIn("soft substance", spread["English Meaning"])
        self.assertIn("untar mantequilla", spread["Spanish Example"])

    def test_spanish_active_examples_use_selected_target_sense(self):
        """Test active Spanish 4000 fixes do not drift back to mismatched examples."""
        path = Path("generated/spanish_full/english_spanish_review.tsv")
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                row["English"]: row
                for row in csv.DictReader((line for line in handle if not line.startswith("#")), delimiter="\t")
            }

        expected = {
            "enjoy": ("disfrutar", "disfruta"),
            "issue": ("el tema", "temas importantes"),
            "fashionable": ("de moda", "muy de moda"),
            "often": ("a menudo", "a menudo"),
            "still": ("aún", "Aún siguen"),
            "single": ("solo", "sola llave"),
            "tear": ("rasgar", "rasgar papel"),
            "eventually": ("finalmente", "Finalmente"),
            "happen": ("dar la casualidad", "Dio la casualidad"),
            "home": ("la casa", "en casa"),
            "chemical": ("el producto químico", "productos químicos"),
            "laugh": ("la risa", "risa llenó"),
            "exercise": ("hacer ejercicio", "hacer ejercicio"),
            "busy": ("ocupado", "está ocupado"),
            "border": ("el borde", "un borde verde"),
            "satisfy": ("satisfacer", "satisfará"),
            "lead": ("guiar", "guiaré"),
            "perform": ("interpretar", "interpretará"),
            "motion": ("el gesto", "un gesto"),
            "period": ("la época", "una época"),
            "range": ("la gama", "una gama"),
        }
        for english, (spanish, example_fragment) in expected.items():
            self.assertEqual(spanish, rows[english]["Spanish"])
            self.assertIn(example_fragment, rows[english]["Spanish Example"])
        self.assertEqual("", rows["often"]["Spanish Article"])
        self.assertEqual("", rows["fashionable"]["Spanish Article"])
        self.assertEqual("", rows["happen"]["Spanish Article"])
        self.assertEqual("", rows["still"]["Spanish Article"])

    def test_spanish_glossary_no_repeated_definition_pairs(self):
        """Test Spanish reviewed meanings avoid obvious repeated-word definitions."""
        paths = [
            Path("generated/spanish_reviewed_glossary_full.tsv"),
            Path("generated/spanish_full/english_spanish_review.tsv"),
        ]
        bad_rows = []
        for path in paths:
            with path.open(encoding="utf-8", newline="") as handle:
                rows = csv.DictReader(handle, delimiter="\t")
                for row in rows:
                    spanish_fields = [
                        row.get("spanish_meaning") or row.get("Spanish Meaning") or "",
                        row.get("spanish_example") or row.get("Spanish Example") or "",
                    ]
                    text = " | ".join(spanish_fields).lower()
                    if re.search(r"\b(\w{4,})\b\s+(o|y)\s+\1\b", text):
                        bad_rows.append((path.name, row.get("english") or row.get("English"), text))

        self.assertEqual([], bad_rows[:20])

    def test_4000_difficulty_order_starts_with_book_one_not_extra(self):
        """Test production rollout uses curriculum order instead of raw Extra-first file order."""
        source_rows = [
            {"deck": "4000 Essential English Words::Extra", "card_number": "2_1", "english_word": "backpack"},
            {"deck": "4000 Essential English Words::1.Book", "card_number": "", "english_word": "agree"},
            {"deck": "4000 Essential English Words::2.Book", "card_number": "", "english_word": "because"},
        ]
        order = sync_4000_production_to_anki.difficulty_order(source_rows)
        self.assertEqual(order["4000 Essential English Words::1.Book::::agree"], 1)
        self.assertEqual(order["4000 Essential English Words::1.Book::row-0002::agree"], 1)
        self.assertEqual(order["4000 Essential English Words::2.Book::::because"], 2)
        self.assertEqual(order["4000 Essential English Words::Extra::2_1::backpack"], 3)

    def test_spanish_production_cue_requires_article_for_nouns(self):
        """Test noun production cues ask for English article but answer includes Spanish article."""
        fields = {
            "English": {"value": "backpack"},
            "Spanish": {"value": "la mochila"},
            "SpanishPartOfSpeech": {"value": "noun"},
        }
        self.assertEqual(sync_4000_production_to_anki.spanish_production_cue(fields), "the backpack")
        self.assertIn("{{type:ProductionAnswer}}", sync_4000_production_to_anki.SPANISH_PRODUCTION_FRONT)
        self.assertNotIn("{{Image}}", sync_4000_production_to_anki.SPANISH_PRODUCTION_FRONT)

    def test_spanish_4000_templates_are_spanish_first_with_english_rescue(self):
        """Test Spanish 4000 backs do not put English beside Spanish learning content."""
        for template in (
            sync_4000_production_to_anki.SPANISH_RECOGNITION_BACK,
            sync_4000_production_to_anki.SPANISH_PRODUCTION_BACK,
            sync_4000_production_to_anki.SPANISH_CONTEXT_PRODUCTION_BACK,
        ):
            before_rescue, rescue = template.split('<details class="rescue">', 1)
            self.assertIn("{{SpanishMeaning}}", before_rescue)
            self.assertIn("{{SpanishExample}}", before_rescue)
            self.assertNotIn("{{English}}", before_rescue)
            self.assertNotIn("{{EnglishMeaning}}", before_rescue)
            self.assertNotIn("{{EnglishExample}}", before_rescue)
            self.assertIn("{{English}}", rescue)

    def test_spanish_context_production_masks_target_without_english_or_image(self):
        """Test Spanish-context production forces recall from Spanish data."""
        fields = {
            "Spanish": {"value": "la mochila"},
            "SpanishMeaning": {"value": "La mochila es una bolsa para llevar objetos."},
            "SpanishExample": {"value": "Guardo mis libros en la mochila."},
        }
        cue = sync_4000_production_to_anki.spanish_context_cue(fields)
        self.assertIn("_____", cue)
        self.assertNotIn("mochila", cue.lower())
        self.assertNotIn("{{English", sync_4000_production_to_anki.SPANISH_CONTEXT_PRODUCTION_FRONT)
        self.assertNotIn("{{Image}}", sync_4000_production_to_anki.SPANISH_CONTEXT_PRODUCTION_FRONT)
        self.assertIn("{{type:ProductionAnswer}}", sync_4000_production_to_anki.SPANISH_CONTEXT_PRODUCTION_FRONT)

    def test_spanish_core_back_prioritizes_pattern_before_support_note(self):
        """Test Spanish Core back shows formula/examples before explanatory support text."""
        template = sync_spanish_core_to_anki.BACK_TEMPLATE
        self.assertLess(template.index("Formula"), template.index("Support note"))
        self.assertLess(template.index("Examples"), template.index("Support note"))
        self.assertNotIn("<div class=\"label\">Note</div>", template)

    def test_english_turkish_cues_do_not_define_word_with_itself(self):
        """Test Turkish production cues avoid tautologies or answer-leaking cognates."""
        path = Path("generated/english_4000/english_turkish_production.tsv")
        if not path.exists():
            self.skipTest("English Turkish production TSV is not generated")

        answer_leaking_starts = {
            "bomba,",
            "etc.",
            "liste,",
            "partneriniz",
            "tramvay, tramvay",
        }
        weak_tautologies = {
            "bir konu önemli bir konudur",
            "insanlar insandır",
            "şanslıysanız şanslısınız",
            "mutluysan mutlusundur",
            "onları çok şaşırtmaktır",
            "yemek yediği bir iştir",
            "ankettir",
        }
        bad_rows = []
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                cue = row.get("TurkishCue", "").strip().lower()
                if re.search(r"^(\w+mak|\w+mek),? .+\1", cue):
                    bad_rows.append((row.get("English"), row.get("TurkishCue")))
                if "varmak bir yere varmaktır" in cue or "görünmek, görünmektir" in cue:
                    bad_rows.append((row.get("English"), row.get("TurkishCue")))
                if any(cue.startswith(prefix) for prefix in answer_leaking_starts):
                    bad_rows.append((row.get("English"), row.get("TurkishCue")))
                if any(phrase in cue for phrase in weak_tautologies):
                    bad_rows.append((row.get("English"), row.get("TurkishCue")))

        self.assertEqual([], bad_rows[:10])

    def test_english_turkish_cue_source_uses_headword_not_definition(self):
        """Test English production cues translate the target word, not its full definition."""
        verb = {
            "english_word": "understand",
            "english_meaning": "To understand is to know what something means.",
        }
        noun = {
            "english_word": "photograph",
            "english_meaning": "A photograph is a picture made with a camera.",
        }
        adjective = {
            "english_word": "terrible",
            "english_meaning": "If something is terrible, it is very bad.",
        }
        self.assertEqual("to understand", generate_english_turkish_cues.cue_source(verb))
        self.assertEqual("photograph", generate_english_turkish_cues.cue_source(noun))
        self.assertEqual("to be terrible", generate_english_turkish_cues.cue_source(adjective))

    def test_english_turkish_cues_are_compact_native_cues(self):
        """Test refreshed Turkish cues are compact L1 cues, not translated English definitions."""
        path = Path("generated/english_4000/english_turkish_production.tsv")
        if not path.exists():
            self.skipTest("English Turkish production TSV is not generated")

        expected = {
            "understand": "anlamak",
            "terrible": "korkunç",
            "photograph": "fotoğraf",
            "shape": "şekil",
            "suppose": "sanmak",
            "instead": "yerine",
            "none": "hiçbiri",
            "issue": "mesele",
            "patient": "sabırlı",
            "calm": "sakin",
            "alien": "uzaylı",
            "capital": "başkent",
        }
        rows = {}
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                rows.setdefault(row["English"].lower(), row)

        for english, turkish in expected.items():
            self.assertEqual(turkish, rows[english]["TurkishCue"].strip().lower())
            self.assertLessEqual(
                len(rows[english]["TurkishCue"].split()),
                3,
                f"{english} has a definition-shaped cue: {rows[english]['TurkishCue']}",
            )

    def test_active_english_turkish_production_cues_are_unique(self):
        """Test active English production fronts are not ambiguous duplicate Turkish cues."""
        path = Path("generated/english_4000/english_turkish_production.tsv")
        if not path.exists():
            self.skipTest("English Turkish production TSV is not generated")

        cues = defaultdict(list)
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                if int(row["Order"]) <= 400:
                    cues[row["TurkishCue"].strip().lower()].append(row["English"])

        duplicates = {cue: words for cue, words in cues.items() if len(words) > 1}
        self.assertEqual({}, duplicates)

    def test_english_turkish_cues_disambiguate_contextless_extra_words(self):
        """Test contextless Extra rows use source-specific cues for ambiguous vocabulary."""
        path = Path("generated/english_4000/english_turkish_production.tsv")
        if not path.exists():
            self.skipTest("English Turkish production TSV is not generated")

        expected = {
            ("4000 Essential English Words::Extra", "2_6", "boxers"): "boxer külot",
            ("4000 Essential English Words::Extra", "2_7", "cap"): "şapka",
            ("4000 Essential English Words::Extra", "2_40", "suit"): "takım elbise",
            ("4000 Essential English Words::Extra", "2_45", "tie"): "kravat",
            ("4000 Essential English Words::Extra", "3_52", "cricket"): "cırcır böceği",
            ("4000 Essential English Words::Extra", "3_80", "beef"): "sığır eti",
            ("4000 Essential English Words::Extra", "3_116", "football"): "amerikan futbolu",
            ("4000 Essential English Words::Extra", "3_30", "seal"): "fok",
            ("4000 Essential English Words::Extra", "3_42", "mole"): "köstebek",
            ("4000 Essential English Words::Extra", "1_1_2", "temple"): "şakak",
            ("4000 Essential English Words::Extra", "1_1_22", "stomach"): "mide",
            ("4000 Essential English Words::Extra", "1_1_34", "palm"): "avuç içi",
            ("4000 Essential English Words::Extra", "1_1_40", "back"): "sırt",
            ("4000 Essential English Words::Extra", "1_1_41", "hip"): "kalça",
            ("4000 Essential English Words::Extra", "1_1_42", "bottom"): "kalça",
            ("4000 Essential English Words::Extra", "1_1_75", "navy"): "lacivert",
            ("4000 Essential English Words::1.Book", "", "capital"): "başkent",
            ("4000 Essential English Words::1.Book", "", "football"): "amerikan futbolu",
            ("4000 Essential English Words::3.Book", "", "found"): "kurmak",
            ("4000 Essential English Words::4.Book", "", "tie"): "bağlamak",
            ("4000 Essential English Words::4.Book", "", "found"): "dayandırmak",
        }
        rows = {}
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                rows[(row["SourceDeck"], row["SourceCard"], row["English"].lower())] = row

        for key, turkish in expected.items():
            self.assertEqual(turkish, rows[key]["TurkishCue"])

    def test_english_turkish_cues_do_not_use_spanish_words(self):
        """Test Turkish production cues do not accidentally contain Spanish translations."""
        path = Path("generated/english_4000/english_turkish_production.tsv")
        if not path.exists():
            self.skipTest("English Turkish production TSV is not generated")

        spanish_looking_cues = {
            "hasta",
            "pero",
            "porque",
            "aunque",
            "desde",
            "hacia",
        }
        bad_rows = []
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                cue = row["TurkishCue"].strip().lower()
                meaning = row["EnglishMeaning"].lower()
                if cue == "hasta" and ("sick" in meaning or "not doing well" in meaning):
                    continue
                if cue in spanish_looking_cues:
                    bad_rows.append((row["English"], row["TurkishCue"]))

        self.assertEqual([], bad_rows)

    def test_spanish_cues_do_not_define_word_with_itself(self):
        """Test Spanish definitions avoid tautologies like 'acercarse significa acercarse'."""
        path = Path("generated/spanish_reviewed_glossary_full.tsv")
        if not path.exists():
            self.skipTest("Spanish reviewed glossary TSV is not generated")

        weak_tautologies = {
            "acercarse significa acercarse",
            "la fuerza es la fuerza",
            "es el problema",
            "una fila es una fila",
            "una cantidad es una cierta cantidad",
            "cenar significa cenar",
            "donar es donar",
            "doble significa el doble o el doble",
            "una meta es una meta",
            "la altura es la altura",
            "una etiqueta es una etiqueta",
            "una empresa es una empresa",
            "un tipo es un tipo",
            "significar significa",
            "inclinar algo significa inclinarlo",
        }
        bad_rows = []
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                meaning = row.get("spanish_meaning", "").strip().lower()
                if any(phrase in meaning for phrase in weak_tautologies):
                    bad_rows.append((row.get("english"), row.get("spanish"), row.get("spanish_meaning")))

        self.assertEqual([], bad_rows[:10])

    def test_rule_cards_do_not_duplicate_answer_as_formula(self):
        """Test rule cards do not render the same formula twice on the back."""
        paths = [
            Path("generated/english_mastery/english_mastery.tsv"),
            Path("generated/spanish_core/spanish_core_learning.tsv"),
        ]
        bad_rows = []
        for path in paths:
            if not path.exists():
                continue
            with path.open(encoding="utf-8", newline="") as handle:
                rows = [line for line in handle if not line.startswith("#")]
            for row in csv.DictReader(rows, delimiter="\t"):
                if row.get("CardType") == "rule" and row.get("Formula", "").strip() == row.get("Answer", "").strip():
                    bad_rows.append((path.name, row.get("SourceID"), row.get("Answer")))

        self.assertEqual([], bad_rows[:10])

    def test_grammar_cards_use_lexical_cues_for_full_forms(self):
        """Test full-form grammar cards give lexical cues instead of broken auxiliary fragments."""
        fronts = "\n".join(card["front"] for card in grammar_levels.get_cards())
        expected = [
            "Cue: look",
            "Cue: check",
            "Cue: lock",
            "Cue: avoid",
        ]
        for marker in expected:
            self.assertIn(marker, fronts)
        self.assertNotIn("are you been", fronts)
        self.assertNotIn("<br>B) has<br>", fronts)

    @patch('urllib.request.urlopen')
    def test_get_word_data(self, mock_urlopen):
        """Test fetching dictionary data with mocked API response."""
        mock_response = MagicMock()
        mock_json = [
            {
                "word": "test",
                "phonetic": "/test/",
                "meanings": [
                    {
                        "definitions": [
                            {
                                "definition": "a trial or experiment",
                                "example": "This is a test case."
                            }
                        ]
                    }
                ]
            }
        ]
        mock_response.read.return_value = json.dumps(mock_json).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        data = anki_tools.get_word_data("test")
        self.assertEqual(data["ipa"], "/test/")
        self.assertEqual(data["meaning"], "a trial or experiment")
        self.assertIn("<b>test</b>", data["example"])

    @patch('subprocess.run')
    def test_generate_audio_logic(self, mock_run):
        """Test the audio generation command sequence."""
        # Mocking open to simulate file presence for the base64 conversion
        with patch("builtins.open", unittest.mock.mock_open(read_data=b"audio_data")):
            with patch("os.path.exists", return_value=True):
                with patch("os.remove"):
                    data = anki_tools.generate_audio_base64("hello", "tmp")
                    self.assertIsNotNone(data)
                    # Verify say and ffmpeg were called
                    self.assertEqual(mock_run.call_count, 2)
                    args1 = mock_run.call_args_list[0][0][0]
                    args2 = mock_run.call_args_list[1][0][0]
                    self.assertEqual(args1[0], "say")
                    self.assertEqual(args2[0], "ffmpeg")

    def test_find_note_id_formatting(self):
        """Test that the Anki search query is properly formatted."""
        with patch('anki_tools.invoke') as mock_invoke:
            mock_invoke.return_value = [12345]
            note_id = anki_tools.find_note_id("apple")
            self.assertEqual(note_id, 12345)
            mock_invoke.assert_called_with("findNotes", query='"Word:apple"')

if __name__ == "__main__":
    unittest.main()
