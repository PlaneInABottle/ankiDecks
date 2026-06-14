import unittest
import csv
import io
from unittest.mock import patch, MagicMock
import os
import json
import re
import tempfile
from pathlib import Path
from collections import Counter

# Import functions from scripts if possible, or we can test the CLI behavior
# Since the scripts are mostly monolithic main blocks, we will test the key logic functions

import check_word
import get_pexels_image
import anki_tools
import grammar_levels
import spanish_deck


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
        cards = grammar_levels.get_cards(level="level_2")
        self.assertTrue(cards)
        self.assertTrue(all(card["level"] == "level_2" for card in cards))

        cloze_cards = grammar_levels.get_cards(level="level_2", card_type="cloze")
        self.assertTrue(cloze_cards)
        self.assertTrue(all(card["card_type"] == "cloze" for card in cloze_cards))

        basic_cards = grammar_levels.get_cards(card_type="basic")
        self.assertTrue(all(card["card_type"] in {"rule", "correction"} for card in basic_cards))

    def test_grammar_level_minimum_counts(self):
        """Test per-level card mix covers minimum rule, cloze, and correction counts."""
        summary = {item["id"]: item["card_count"] for item in grammar_levels.get_level_summary()}
        total_cards = 0
        min_per_level = {
            "level_1": 130,
            "level_2": 170,
            "level_3": 170,
            "level_4": 120,
            "level_5": 120,
        }
        for level in grammar_levels.LEVELS:
            cards = grammar_levels.get_cards(level=level["id"])
            by_type = Counter(card["card_type"] for card in cards)

            self.assertGreaterEqual(len(cards), min_per_level[level["id"]], f"Too few cards for {level['id']}.")
            self.assertIn("rule", by_type)
            self.assertIn("cloze", by_type)
            self.assertIn("correction", by_type)
            self.assertGreaterEqual(by_type["rule"], 1)
            self.assertGreaterEqual(by_type["cloze"], 1)
            self.assertGreaterEqual(by_type["correction"], 1)
            self.assertEqual(by_type["rule"] + by_type["cloze"] + by_type["correction"], len(cards))
            self.assertEqual(summary[level["id"]], len(cards))
            total_cards += len(cards)

        self.assertGreaterEqual(total_cards, 800)

    def test_grammar_tsv_renderers(self):
        """Test renderer boundaries for Basic and Cloze outputs."""
        cards = grammar_levels.get_cards()
        by_type = Counter(card["card_type"] for card in cards)
        basic_tsv = grammar_levels.render_basic_tsv(cards)
        cloze_tsv = grammar_levels.render_cloze_tsv(cards)

        self.assertIn("Front\tBack\tTags", basic_tsv)
        self.assertIn("Text\tExtra\tTags", cloze_tsv)
        self.assertNotIn("{{c1::", basic_tsv)
        self.assertIn("{{c1::", cloze_tsv)

        basic_reader = csv.reader(io.StringIO(basic_tsv), delimiter="\t")
        basic_rows = [row for row in basic_reader if row and not row[0].startswith("#")]
        cloze_reader = csv.reader(io.StringIO(cloze_tsv), delimiter="\t")
        cloze_rows = [row for row in cloze_reader if row and not row[0].startswith("#")]

        self.assertEqual(len(basic_rows), by_type["rule"] + by_type["correction"] + 1)
        self.assertEqual(len(cloze_rows), by_type["cloze"] + 1)

    def test_grammar_formula_cards_exist(self):
        """Test explicit grammar formula cards for requested tense/modal/conditional systems."""
        rule_cards = grammar_levels.get_cards(card_type="rule")
        all_back_text = " | ".join(card["back"].lower() for card in rule_cards)
        expected_markers = [
            "subject + v1",
            "am / is / are + v-ing",
            "did + subject + v1",
            "was / were + v-ing",
            "have/has + v3",
            "had + v3",
            "will + v1",
            "going to + v1",
            "will have + v3",
            "be + v3",
            "modal + v1",
            "modal + have + v3",
            "if + present simple, present simple",
            "if + present simple, will + v1",
            "if + v2, would + v1",
            "if + had + v3, would have + v3",
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

    def test_grammar_passive_cards_agreement(self):
        """Test expected passive be + participle agreement in level 3 cloze cards."""
        cards = [
            card
            for card in grammar_levels.get_cards(level="level_3")
            if card["card_type"] == "cloze" and card["topic"] == "passive voice"
        ]
        self.assertTrue(cards)
        requirements = {
            "The files": "were",
            "The letters": "were",
            "The meetings": "were",
            "The report": "was",
            "The team": "was",
            "The project": "was",
            "The door": "was",
        }
        for subject, expected_aux in requirements.items():
            prefix = f"{subject} {{{{c1::{expected_aux}"
            matching = [card for card in cards if card["text"].startswith(prefix)]
            self.assertTrue(
                matching,
                f"No passive cloze card found for subject '{subject}' with auxiliary '{expected_aux}'.",
            )

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

    def test_all_cloze_cards_use_cloze_markup(self):
        """Test every cloze card can generate an Anki cloze deletion."""
        cloze_cards = grammar_levels.get_cards(card_type="cloze")
        self.assertTrue(cloze_cards)
        for card in cloze_cards:
            self.assertIn("{{c", card["text"])
            self.assertIn("::", card["text"])

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
            self.assertIn("Front\tBack\tTags", basic)
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

            self.assertEqual(len(basic_rows), by_type["rule"] + by_type["correction"] + 1)
            self.assertEqual(len(cloze_rows), by_type["cloze"] + 1)

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
            self.assertEqual(rows[1]["spanish"], "armada")

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
                    "Spanish Meaning",
                    "Spanish Example",
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
            self.assertEqual(basic_data[1][0], '<img src="apple.jpg" />\nmanzana')
            back = basic_data[1][1]
            self.assertIn("English: apple", back)
            self.assertIn("Meaning: fruta", back)
            self.assertIn("Example: La manzana es roja.", back)
            self.assertIn("English source:", back)
            self.assertIn("An apple is a fruit.", back)
            self.assertIn("The apple is red.", back)
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
