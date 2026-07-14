import unittest
import csv
import io
from unittest.mock import patch, MagicMock
import os
import json
import html
import re
import tempfile
from pathlib import Path
from collections import Counter, defaultdict

# Import functions from scripts if possible, or we can test the CLI behavior
# Since the scripts are mostly monolithic main blocks, we will test the key logic functions

import check_word
import get_pexels_image
import anki_protect
import anki_tools
import grammar_levels
import spanish_grammar_levels
import spanish_core_learning
import spanish_deck
import sync_spanish_core_to_anki
import sync_english_mastery_to_anki
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

    def test_fingerprint_distinguishes_source_updates_from_manual_edits(self):
        """Tracked source drift is safe, but live drift is protected."""
        field_names = ["Front", "Back"]
        old_source = {"Front": "old front", "Back": "old back"}
        new_source = {"Front": "new front", "Back": "new back"}
        tracked_live = {
            "Front": {"value": "old front"},
            "Back": {"value": "old back"},
            anki_protect.FINGERPRINT_FIELD: {
                "value": anki_protect.content_fingerprint(old_source, field_names)
            },
        }

        self.assertFalse(
            anki_protect.note_has_untracked_edits(tracked_live, new_source, field_names)
        )
        tracked_live["Front"]["value"] = "my edited front"
        self.assertTrue(
            anki_protect.note_has_untracked_edits(tracked_live, new_source, field_names)
        )

    def test_legacy_note_is_only_safe_when_it_matches_source(self):
        """Unfingerprinted notes are never overwritten when their content differs."""
        field_names = ["Front", "Back"]
        source = {"Front": "front", "Back": "back"}
        matching = {"Front": {"value": "front"}, "Back": {"value": "back"}}
        edited = {"Front": {"value": "my front"}, "Back": {"value": "back"}}

        self.assertFalse(anki_protect.note_has_untracked_edits(matching, source, field_names))
        self.assertTrue(anki_protect.note_has_untracked_edits(edited, source, field_names))

    def test_legacy_generated_fingerprint_allows_first_safe_source_update(self):
        """A known prior generated version migrates, while a manual variant locks."""
        field_names = ["Front", "Back"]
        old_source = {"Front": "old front", "Back": "old back"}
        new_source = {"Front": "new front", "Back": "new back"}
        old_fingerprint = anki_protect.content_fingerprint(old_source, field_names)
        generated_live = {
            "Front": {"value": "old front"},
            "Back": {"value": "old back"},
        }
        manual_live = {
            "Front": {"value": "my old front"},
            "Back": {"value": "old back"},
        }

        self.assertFalse(
            anki_protect.note_has_untracked_edits(
                generated_live,
                new_source,
                field_names,
                legacy_fingerprints=(old_fingerprint,),
            )
        )
        self.assertTrue(
            anki_protect.note_has_untracked_edits(
                manual_live,
                new_source,
                field_names,
                legacy_fingerprints=(old_fingerprint,),
            )
        )

    def test_legacy_manifest_covers_changed_generated_content(self):
        anki_protect.load_legacy_fingerprints.cache_clear()
        namespaces = anki_protect.load_legacy_fingerprints()

        self.assertGreater(len(namespaces["spanish_core"]), 0)
        self.assertGreater(len(namespaces["english_mastery"]), 0)
        self.assertGreater(len(namespaces["spanish_4000_content"]), 1000)
        self.assertGreater(len(namespaces["spanish_4000_production"]), 0)
        self.assertGreater(len(namespaces["english_4000_production"]), 0)
        for entries in namespaces.values():
            for fingerprint in entries.values():
                self.assertRegex(fingerprint, r"^[0-9a-f]{64}$")

    def test_spanish_core_sync_auto_locks_legacy_manual_edit(self):
        """Bulk sync locks and preserves a differing legacy note while still moving it."""
        row = {field: "" for field in sync_spanish_core_to_anki.FIELDS}
        row.update({"SourceID": "core::1", "DeckPath": "Spanish Core::A1", "Front": "source", "Tags": "core"})
        live_fields = {
            field: {"value": value}
            for field, value in row.items()
        }
        live_fields["Front"] = {"value": "my edited front"}
        note = {"noteId": 42, "fields": live_fields, "tags": []}

        def fake_invoke(action, **params):
            if action == "findCards":
                return [420]
            return None

        with patch.object(sync_spanish_core_to_anki, "load_existing_notes", return_value={"core::1": note}), \
             patch.object(sync_spanish_core_to_anki, "invoke", side_effect=fake_invoke) as mock_invoke:
            result = sync_spanish_core_to_anki.sync_rows([row], store_media=False)

        self.assertEqual(result["auto_locked"], 1)
        self.assertEqual(result["updated"], 0)
        self.assertIn(
            unittest.mock.call("addTags", notes=[42], tags=anki_protect.LOCKED_TAG),
            mock_invoke.call_args_list,
        )
        self.assertNotIn("updateNoteFields", [call.args[0] for call in mock_invoke.call_args_list])
        self.assertIn("changeDeck", [call.args[0] for call in mock_invoke.call_args_list])

    def test_stale_legacy_note_is_not_pruned_without_fingerprint(self):
        """Pruning cannot prove a legacy note is unedited, so it leaves it alone."""
        note = {
            "noteId": 42,
            "tags": [],
            "fields": {"SourceID": {"value": "removed::1"}, "Front": {"value": "front"}},
        }

        def fake_invoke(action, **params):
            if action == "findNotes":
                return [42]
            if action == "notesInfo":
                return [note]
            return None

        with patch.object(sync_spanish_core_to_anki, "invoke", side_effect=fake_invoke) as mock_invoke:
            pruned = sync_spanish_core_to_anki.prune_stale_notes(set())

        self.assertEqual(pruned, 0)
        self.assertNotIn("deleteNotes", [call.args[0] for call in mock_invoke.call_args_list])

    def test_word_update_with_blank_prompts_keeps_live_fields(self):
        """Blank prompts do not replace a live card with fetched suggestions."""
        current = {
            "Meaning": "my meaning",
            "Example": "My <b>apple</b> example",
            "IPA": "/mine/",
        }
        fetched = {"meaning": "fetched meaning", "example": "Fetched apple example", "ipa": "/fetched/"}

        with patch("sys.argv", ["anki_tools.py", "apple"]), \
             patch.object(anki_tools, "find_note_id", return_value=42), \
             patch.object(anki_tools, "get_note_fields", return_value=current), \
             patch.object(anki_tools, "get_word_data", return_value=fetched), \
             patch("builtins.input", side_effect=["y", "", "", ""]), \
             patch.object(anki_tools, "generate_audio_base64") as mock_audio, \
             patch.object(anki_tools, "invoke") as mock_invoke:
            anki_tools.main()

        mock_audio.assert_not_called()
        self.assertNotIn("updateNoteFields", [call.args[0] for call in mock_invoke.call_args_list])

    def test_word_update_rolls_back_only_text_whose_audio_failed(self):
        """Changed text and its audio update as one pair, without stale sound."""
        current = {
            "Meaning": "old meaning",
            "Example": "Old <b>apple</b> example",
            "IPA": "/old/",
        }
        fetched = {"meaning": "fetched", "example": "Fetched apple", "ipa": "/fetched/"}

        with patch("sys.argv", ["anki_tools.py", "apple"]), \
             patch.object(anki_tools, "find_note_id", return_value=42), \
             patch.object(anki_tools, "get_note_fields", return_value=current), \
             patch.object(anki_tools, "get_word_data", return_value=fetched), \
             patch("builtins.input", side_effect=["y", "new meaning", "New apple example", ""]), \
             patch.object(
                 anki_tools,
                 "generate_audio_base64",
                 side_effect=[None, "ZXhhbXBsZS1hdWRpbw=="],
             ), \
             patch.object(anki_tools, "invoke") as mock_invoke:
            anki_tools.main()

        update_calls = [
            call for call in mock_invoke.call_args_list if call.args[0] == "updateNoteFields"
        ]
        self.assertEqual(1, len(update_calls))
        updated_fields = update_calls[0].kwargs["note"]["fields"]
        self.assertNotIn("Meaning", updated_fields)
        self.assertNotIn("Sound_Meaning", updated_fields)
        self.assertEqual("New <b>apple</b> example", updated_fields["Example"])
        self.assertEqual("[sound:user_apple_example.mp3]", updated_fields["Sound_Example"])

    def test_existing_model_presentation_is_preserved_by_default(self):
        """Adding sync metadata does not replace an existing template or CSS."""
        def fake_invoke(action, **params):
            if action == "modelNames":
                return [sync_spanish_core_to_anki.MODEL_NAME]
            if action == "modelFieldNames":
                return list(sync_spanish_core_to_anki.MODEL_FIELDS)
            return None

        with patch.object(sync_spanish_core_to_anki, "invoke", side_effect=fake_invoke) as mock_invoke:
            sync_spanish_core_to_anki.ensure_model()

        actions = [call.args[0] for call in mock_invoke.call_args_list]
        self.assertNotIn("updateModelTemplates", actions)
        self.assertNotIn("updateModelStyling", actions)

    def test_production_sync_auto_locks_manual_cue_edit(self):
        """Derived production fields receive the same overwrite protection."""
        fields = {
            "SourceID": {"value": "4000 Essential English Words::1.Book::::apple"},
            "English": {"value": "apple"},
            "Spanish": {"value": "la manzana"},
            "SpanishPartOfSpeech": {"value": "noun"},
            "ProductionCue": {"value": "my custom cue"},
        }
        note = {"noteId": 7, "fields": fields, "cards": [], "tags": []}
        order_map = {"4000 Essential English Words::1.Book::::apple": 1}

        with patch.object(sync_4000_production_to_anki, "get_notes", return_value=[note]), \
             patch.object(sync_4000_production_to_anki, "update_note_fields_many") as mock_update, \
             patch.object(sync_4000_production_to_anki, "card_maps_for_notes", return_value={}), \
             patch.object(sync_4000_production_to_anki, "apply_card_plan"), \
             patch.object(sync_4000_production_to_anki, "invoke") as mock_invoke:
            result = sync_4000_production_to_anki.sync_spanish(
                order_map, active_limit=400, context_active_limit=0
            )

        self.assertEqual(result["auto_locked"], 1)
        self.assertEqual(result["typing_enabled_locked"], 1)
        mock_update.assert_called_once_with([(7, {"ProductionAnswer": "la manzana"})])
        mock_invoke.assert_called_once_with("addTags", notes=[7], tags=anki_protect.LOCKED_TAG)

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

    def test_spanish_core_formulas_teach_decision_rules(self):
        """Test Spanish Core formulas teach the grammar decision, not only a label."""
        cards = spanish_core_learning.get_cards()
        rule_like = [
            card for card in cards
            if card["CardType"] in {
                "rule",
                "typed_contrast",
                "typed_correction",
                "interleaved_contrast",
                "typed_cloze",
                "audio_cloze",
            }
        ]
        self.assertGreaterEqual(len(rule_like), 900)
        for card in rule_like:
            self.assertIn("Decision rule", card["Formula"], card["SourceID"])
            self.assertIn("Pattern", card["Formula"], card["SourceID"])
            self.assertNotIn("Choose the right form for each context", card["Formula"], card["SourceID"])
            self.assertNotIn("retrieve from sound and context", card["Formula"], card["SourceID"])
            self.assertNotIn("retrieve the missing chunk from context", card["Formula"], card["SourceID"])

        por_para = next(
            card for card in cards
            if card["SourceID"] == "interleaved::a2_2_natural_spanish::por_vs_para_reason_vs_purpose::1"
        )
        self.assertIn("para for purpose", por_para["Formula"])
        self.assertIn("por for reason", por_para["Formula"])

        subjunctive = next(
            card for card in cards
            if card["SourceID"] == "interleaved::b1_bridge::indicative_vs_subjunctive_fact_vs_doubt::1"
        )
        self.assertIn("indicative after belief", subjunctive["Formula"])
        self.assertIn("subjunctive after doubt", subjunctive["Formula"])

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

    def test_spanish_audio_dictation_is_full_sentence_listening(self):
        """Test dictation cards reconstruct a whole sentence without written context."""
        cards = [
            card for card in spanish_core_learning.get_cards()
            if card["SourceID"].startswith("tatoeba_dictation::")
        ]
        self.assertGreaterEqual(len(cards), 40)
        for card in cards:
            self.assertEqual(card["CardType"], "dictation")
            self.assertEqual(card["PromptMode"], "type_compare")
            self.assertIn("[sound:tatoeba_spa_", card["Front"])
            self.assertNotIn("_____", card["Front"])
            self.assertIn("type the full Spanish sentence", card["Front"])
            self.assertRegex(card["Answer"], r"\s")

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
            "mochila": "mo-Çİ-la",
            "cinturón": "sin-tu-RON",
            "queso": "KE-so",
            "guitarra": "gi-TAR-ra",
            "llave": "YA-be",
            "jardín": "har-DİN",
            "círculo": "SİR-ku-lo",
            "el cinturón": "el sin-tu-RON",
        }
        for word, expected in examples.items():
            hint = spanish_deck.spanish_pronunciation_hint(word)
            self.assertEqual(hint, expected)
            self.assertNotIn("I", hint)

    def test_spanish_metadata_uses_conservative_forms(self):
        """Test inferred Spanish grammar does not invent risky forms."""
        noun = spanish_deck.infer_spanish_metadata("el cinturón")
        self.assertEqual(noun["spanish_forms"], "singular: el cinturón; plural: los cinturones")
        self.assertIn(
            "plural: los volúmenes",
            spanish_deck.infer_spanish_metadata("el volumen")["spanish_forms"],
        )
        self.assertIn(
            "plural: las imágenes",
            spanish_deck.infer_spanish_metadata("la imagen")["spanish_forms"],
        )

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
        self.assertIn("body part", notes_by_pair[("bottom", "el trasero")])
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
        """Test typed_contrast answers are missing chunks that reconstruct the full sentence."""
        contrast_cards = english_mastery.get_cards(card_type="typed_contrast")
        for card in contrast_cards:
            front = re.sub(r"<br\s*/?>", "\n", card["Front"])
            front = re.sub(r"<[^>]+>", "", front)
            front_lines = [line.strip() for line in front.splitlines() if "_____" in line]
            self.assertEqual(1, len(front_lines), f"Expected one sentence blank line in {card['SourceID']}: {front}")
            front = front_lines[0]
            answer = card["Answer"]
            parts = re.split(r"_{3,}", front, maxsplit=1)
            if len(parts) != 2:
                self.fail(f"No blank found in front: {front[:100]}")
            self.assertLessEqual(
                len(re.findall(r"[A-Za-z']+", answer)),
                5,
                f"Contrast answer should be the missing chunk, not the full sentence: {card['SourceID']} -> {answer}",
            )
            full_sentence_match = re.search(r"Full sentence:\s*(.*)", card["Back"])
            if not full_sentence_match:
                continue
            reconstructed = f"{parts[0]}{answer}{parts[1]}"
            reconstructed = re.sub(r"[,;:]", "", reconstructed)
            reconstructed = re.sub(r"\s+", " ", reconstructed).strip().lower().rstrip(".")
            expected = html.unescape(re.sub(r"\s+", " ", full_sentence_match.group(1)))
            expected = re.sub(r"[,;:]", "", expected).strip().lower().rstrip(".")
            self.assertEqual(
                expected,
                reconstructed,
                f"Typed chunk does not reconstruct full sentence for {card['SourceID']}",
            )

    def test_english_contrast_lexical_cues_when_needed(self):
        """Test semantically ambiguous grammar cloze cards include useful function/base cues."""
        contrast_cards = english_mastery.get_cards(card_type="typed_contrast")
        grammar_contrasts = [card for card in contrast_cards if card["SourceID"].startswith("grammar::")]
        self.assertTrue(grammar_contrasts)
        for card in grammar_contrasts:
            self.assertTrue(
                "Function" in card["Front"],
                f"Grammar contrast has no cue: {card['SourceID']}",
            )
            self.assertNotIn("Trigger", card["Front"], card["SourceID"])
        reviewed = [
            card for card in contrast_cards
            if "We _____ three versions already this week" in card["Front"]
        ]
        self.assertEqual(len(reviewed), 1)
        self.assertIn("Base", reviewed[0]["Front"])
        self.assertIn("review", reviewed[0]["Front"])
        london = [
            card for card in contrast_cards
            if "I _____ in London since 2018" in card["Front"]
        ]
        self.assertEqual(len(london), 1)
        self.assertIn("Base", london[0]["Front"])
        self.assertIn("live", london[0]["Front"])
        decided = [
            card for card in contrast_cards
            if "They decided _____ another run" in card["Front"]
        ]
        self.assertEqual(len(decided), 1)
        self.assertIn("decide is commonly followed by to + infinitive", decided[0]["Front"])
        self.assertIn("Base", decided[0]["Front"])
        self.assertIn("do", decided[0]["Front"])
        self.assertNotIn("i / live", london[0]["Front"].lower())

    def test_english_contrast_base_cues_do_not_reveal_exact_answer(self):
        """Test base cues guide retrieval without copying the exact typed answer."""
        for card in english_mastery.get_cards(card_type="typed_contrast"):
            if not card["SourceID"].startswith("grammar::"):
                continue
            base_match = re.search(r'<span class="front-label">Base</span>:\s*([^<]+)', card["Front"])
            if not base_match:
                continue
            base = re.sub(r"[^a-z0-9']+", " ", html.unescape(base_match.group(1)).lower()).strip()
            answer = re.sub(r"[^a-z0-9']+", " ", card["Answer"].lower()).strip()
            self.assertNotEqual(answer, base, card["SourceID"])

    def test_english_interleaved_contrasts_are_cued(self):
        """Test paired contrast prompts include a cue for each blanked sentence."""
        cards = english_mastery.get_cards(card_type="interleaved_contrast")
        self.assertGreaterEqual(len(cards), 20)
        for card in cards:
            blanks = re.findall(r"_{4,}", card["Front"])
            cues = re.findall(r"<span class=\"front-cue\">", card["Front"])
            self.assertGreaterEqual(len(blanks), 2, card["SourceID"])
            self.assertGreaterEqual(len(cues), 2, card["SourceID"])

    def test_english_interleaved_formulas_teach_decision_rules(self):
        """Test paired contrast backs teach how to choose, not just the answer label."""
        cards = {
            card["SourceID"]: card
            for card in english_mastery.get_cards(card_type="interleaved_contrast")
        }

        conditional = cards["interleaved::b2_sentence_control::second_vs_third_conditional::1"]
        self.assertIn("Decision rule", conditional["Formula"])
        self.assertIn("would + base verb", conditional["Formula"])
        self.assertIn("would have + past participle", conditional["Formula"])
        self.assertIn("had had", conditional["Formula"])

        past_perfect = cards["interleaved::b2_tense_system::past_perfect_vs_past_simple::1"]
        self.assertIn("Decision rule", past_perfect["Formula"])
        self.assertIn("had + past participle", past_perfect["Formula"])
        self.assertIn("by the time", past_perfect["Formula"])

    def test_english_grammar_formulas_teach_decision_rules(self):
        """Test generated grammar cards include rule-learning formulas."""
        cards = [
            card for card in english_mastery.get_cards()
            if card["SourceID"].startswith(("grammar::", "grammar_rule::"))
            and card["CardType"] in {"typed_contrast", "rule"}
        ]
        self.assertGreaterEqual(len(cards), 120)
        for card in cards:
            self.assertIn("Decision rule", card["Formula"], card["SourceID"])
            self.assertIn("Pattern", card["Formula"], card["SourceID"])

        causative = next(
            card for card in cards
            if card["SourceID"] == "grammar::b2_verb_patterns::causatives::047::typed_contrast"
        )
        self.assertIn("arranges", causative["Formula"])
        self.assertIn("did not necessarily train them herself", causative["Formula"])

    def test_english_function_cues_do_not_repeat_exact_answer(self):
        """Test grammar/function-word cards use function cues instead of leaking answers."""
        protected_ids = {
            "grammar::b2_sentence_control::noun_clauses::033::typed_contrast",
            "grammar::b2_verb_patterns::modal_verbs::040::typed_contrast",
            "grammar::b2_verb_patterns::modal_verbs::042::typed_contrast",
            "grammar::b2_verb_patterns::causatives::047::typed_contrast",
        }
        cards = {
            card["SourceID"]: card
            for card in english_mastery.get_cards(card_type="typed_contrast")
        }
        for source_id in protected_ids:
            card = cards[source_id]
            self.assertIn("Function", card["Front"], source_id)
            self.assertNotIn("Target cue", card["Front"], source_id)

    def test_english_sentence_mining_rejects_wrong_used_to_sense(self):
        """Test used-to mining rejects purpose/use senses like 'garlic is used to improve'."""
        rejected = [
            {"eng_id": "35858", "text": "Garlic is used to improve the taste of food.", "target": "is used to"},
            {"eng_id": "24040", "text": "Home life was being screened from foreign eyes.", "target": "was being"},
            {"eng_id": "39314", "text": "While the demonstration was being made, the president was taking notes.", "target": "was being"},
            {"eng_id": "246200", "text": "It is provided that the applicants must be woman.", "target": "provided that"},
            {"eng_id": "17878", "text": "By the time you get out of jail, she'll probably have gotten married.", "target": "by the time"},
            {"eng_id": "29672", "text": "Meanwhile, the foolish uncle was sitting in the living room.", "target": "meanwhile"},
            {"eng_id": "264574", "text": "She obviously thought she was a good woman, but...", "target": "obviously"},
            {"eng_id": "2164985", "text": "Meanwhile I can make myself understood.", "target": "meanwhile"},
        ]
        for row in rejected:
            self.assertFalse(english_mastery._valid_sentence_mining_row(row), row["eng_id"])

    def test_english_audio_rejects_low_value_had_card(self):
        """Test low-value listening cloze rows are filtered from cached audio selection."""
        self.assertIn("2037", english_mastery.REJECT_AUDIO_SENTENCE_IDS)

    def test_english_lexical_cues_keep_process_and_timing(self):
        """Test cue lemmatization does not damage process/timing into proces/tim."""
        self.assertEqual(english_mastery._lexical_cue_from_chunk("the process"), "process")
        self.assertEqual(english_mastery._lexical_cue_from_chunk("Timing"), "timing")

    def test_spanish_self_grade_production_prompts_are_clear(self):
        """Test self-graded Spanish production prompts explain that the answer is a model."""
        cards = [
            card for card in spanish_core_learning.get_cards()
            if card["CardType"] == "typed_production" and card["PromptMode"] == "self_grade"
        ]
        self.assertGreater(len(cards), 0)
        for card in cards:
            self.assertIn("Write any valid Spanish sentence or chunk", card["Front"])
            self.assertIn("Model answer", card["Front"])
            self.assertNotIn("Model target", card["Front"])

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

    def test_english_sentence_mining_formulas_explain_target_patterns(self):
        """Test sentence mining cards include the grammar pattern behind the chunk."""
        cards = {
            card["SourceID"]: card
            for card in english_mastery.get_cards(card_type="typed_cloze")
        }

        if_i_had = cards["tatoeba_eng_mining::b2_sentence_control::30443::if_i_had"]
        self.assertIn("Full sentence", if_i_had["Back"])
        self.assertIn("had + past participle", if_i_had["Formula"])
        self.assertIn("had had", if_i_had["Formula"])

        was_being = cards["tatoeba_eng_mining::b2_sentence_control::40170::was_being"]
        self.assertIn("past continuous passive", was_being["Formula"])
        self.assertIn("was/were being + past participle", was_being["Formula"])
        for card in cards.values():
            self.assertIn("Decision rule", card["Formula"], card["SourceID"])
            self.assertIn("Pattern", card["Formula"], card["SourceID"])
            self.assertNotIn("Use the target chunk because", card["Formula"], card["SourceID"])

    def test_sentence_mining_rejects_wrong_grammar_function_matches(self):
        invalid_rows = (
            {"eng_id": "x1", "target": "will have", "text": "We will have to leave."},
            {"eng_id": "x2", "target": "have been", "text": "You should have been careful."},
            {"eng_id": "x3", "target": "used to", "text": "I am used to working late."},
            {"eng_id": "x4", "target": "used to", "text": "I am getting used to it."},
            {"eng_id": "x5", "target": "not only", "text": "Not only you but I was there."},
            {"eng_id": "x6", "target": "in case", "text": "Call me in case of emergency."},
            {"eng_id": "x7", "target": "so that", "text": "It rained, so that we left."},
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                self.assertFalse(english_mastery._valid_sentence_mining_row(row))

    def test_reviewed_sentence_mining_excludes_known_misleading_cards(self):
        source_ids = {card["SourceID"] for card in english_mastery.get_cards()}
        for eng_id in english_mastery.REJECT_SENTENCE_MINING_IDS:
            with self.subTest(eng_id=eng_id):
                self.assertFalse(
                    any(f"::{eng_id}::" in source_id for source_id in source_ids),
                    f"Rejected sentence {eng_id} was still generated",
                )

    def test_sentence_mining_has_no_duplicate_source_sentences(self):
        rows = english_mastery._load_sentence_mining_sentences()
        normalized = [re.sub(r"\s+", " ", row["text"]).strip().casefold() for row in rows]
        self.assertEqual(len(normalized), len(set(normalized)))

    def test_sentence_mining_rules_match_reviewed_target_functions(self):
        cards = english_mastery.get_cards(card_type="typed_cloze")
        it_is_cards = [card for card in cards if card["Answer"] == "it is"]
        self.assertTrue(it_is_cards)
        for card in it_is_cards:
            self.assertIn("impersonal evaluation", card["Front"])
            self.assertIn("not an it-cleft", card["Formula"])

        would_rather = next(
            card for card in cards if card["SourceID"].endswith("::16827::would_rather")
        )
        self.assertIn("subject + past form", would_rather["Formula"])

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

    def test_spanish_metadata_handles_phrases_and_acronyms(self):
        """Test phrase/acronym Spanish rows do not get malformed noun or verb forms."""
        cases = {
            "las artes marciales": ("noun", "singular: el arte marcial; plural: las artes marciales"),
            "el/la director/a": ("noun", "singular: el director / la directora; plural: los directores / las directoras"),
            "el ADN": ("noun", "invariable acronym: el ADN"),
            "la artritis": ("noun", "singular: la artritis; plural: las artritis"),
            "súper": ("adjective/adverb", "invariable: súper"),
        }
        for spanish, (part_of_speech, forms) in cases.items():
            metadata = spanish_deck.infer_spanish_metadata(spanish)
            self.assertEqual(part_of_speech, metadata["spanish_part_of_speech"], spanish)
            self.assertEqual(forms, metadata["spanish_forms"], spanish)

        for phrase in ["por despecho", "a diferencia de", "más allá", "por", "no"]:
            self.assertEqual(phrase, spanish_deck.add_article_to_clear_noun(phrase, phrase, f"{phrase} is a phrase."))

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
            review_path = spanish_deck.write_spanish_files(
                source_rows,
                {},
                output_dir=tmpdir,
                limit=3,
            )
            self.assertTrue(Path(review_path).exists())

            with open(review_path, encoding="utf-8", newline="") as handle:
                review_rows = list(csv.reader(handle, delimiter="\t"))
            review_data = [row for row in review_rows if row and not row[0].startswith("#")]
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

    def test_no_translation_invented_without_glossary(self):
        """Test no Spanish translation is produced when glossary is absent."""
        source_rows = [
            {"english_word": "unverified", "deck": "4000 Essential English Words::Extra", "card_number": "3_1"}
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            rows = spanish_deck.build_spanish_rows(source_rows, {})
            self.assertEqual(rows[0]["status"], spanish_deck.STATUS_NEEDS_TRANSLATION)
            self.assertEqual(rows[0]["spanish"], "")

            spanish_deck.write_spanish_files(source_rows, {}, output_dir=tmpdir)
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

        consist = rows["consist"]
        self.assertEqual(consist["Spanish"], "consistir")
        self.assertIn("made of those parts", consist["English Meaning"])
        self.assertIn("estar formado", consist["Spanish Meaning"])

        self.assertEqual(rows["platform"]["Spanish"], "la plataforma")
        self.assertEqual(rows["equipment"]["Spanish"], "el equipo")
        self.assertIn("set of things", rows["equipment"]["English Meaning"])
        self.assertIn("conjunto de herramientas", rows["equipment"]["Spanish Meaning"])
        self.assertEqual(rows["poor"]["Spanish"], "deficiente")
        self.assertEqual(rows["destruction"]["Spanish"], "la destrucción")
        self.assertIn("serious damage", rows["destruction"]["English Meaning"])
        self.assertIn("comprised of seniors", rows["comprise"]["English Example"])
        self.assertIn("consta principalmente", rows["comprise"]["Spanish Example"])

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
            "dig": ("cavar", "cava"),
            "speed": ("conducir rápido", "Conducir rápido"),
            "citizen": ("el ciudadano", "ciudadano español"),
            "unique": ("único", "único"),
            "release": ("liberar", "liberó"),
            "arrange": ("organizar", "organiza"),
            "sense": ("percibir", "percibir"),
            "settle": ("resolver", "Resolvimos"),
            "demonstrate": ("demostrar", "demostró"),
            "fail": ("fallar", "falló"),
            "across": ("cruzar", "Cruzó"),
        }
        for english, (spanish, example_fragment) in expected.items():
            self.assertEqual(spanish, rows[english]["Spanish"])
            self.assertIn(example_fragment, rows[english]["Spanish Example"])
        self.assertEqual("", rows["often"]["Spanish Article"])
        self.assertEqual("", rows["fashionable"]["Spanish Article"])
        self.assertEqual("", rows["happen"]["Spanish Article"])
        self.assertEqual("", rows["still"]["Spanish Article"])

    def test_spanish_4000_sync_keeps_recognition_suspended(self):
        """Test Spanish 4000 sync only activates production cards."""
        fields = {
            "SourceID": {"value": "4000 Essential English Words::1.Book::::apple"},
            "English": {"value": "apple"},
            "Spanish": {"value": "la manzana"},
            "SpanishPartOfSpeech": {"value": "noun"},
            "SpanishMeaning": {"value": "Fruta roja."},
            "SpanishExample": {"value": "La manzana es roja."},
        }
        note = {"noteId": 1, "fields": fields, "cards": [101, 102, 103]}
        order_map = {"4000 Essential English Words::1.Book::::apple": 1}
        planned = {}

        def fake_apply_card_plan(deck_cards, active_cards, suspended_cards):
            planned["deck_cards"] = deck_cards
            planned["active_cards"] = active_cards
            planned["suspended_cards"] = suspended_cards

        with patch.object(sync_4000_production_to_anki, "get_notes", return_value=[note]), \
             patch.object(sync_4000_production_to_anki, "update_note_fields_many"), \
             patch.object(sync_4000_production_to_anki, "card_maps_for_notes", return_value={1: {0: 101, 1: 102, 2: 103}}), \
             patch.object(sync_4000_production_to_anki, "apply_card_plan", side_effect=fake_apply_card_plan):
            result = sync_4000_production_to_anki.sync_spanish(
                order_map, active_limit=400, context_active_limit=0, force=True
            )

        self.assertEqual(result["recognition_suspended"], 1)
        self.assertEqual(result["production_suspended"], 0)
        self.assertEqual(result["context_suspended"], 1)
        self.assertNotIn(101, planned["active_cards"])
        self.assertIn(101, planned["suspended_cards"])
        self.assertIn(102, planned["active_cards"])
        self.assertNotIn(103, planned["active_cards"])
        self.assertIn(103, planned["suspended_cards"])

    def test_english_4000_sync_keeps_recognition_suspended(self):
        """Test English 4000 sync only activates production cards."""
        fields = {
            "ProductionSourceID": {"value": "4000 Essential English Words::1.Book::::agree"},
            "Word": {"value": "agree"},
        }
        note = {"noteId": 1, "fields": fields, "cards": [201, 202], "cardsInfoDeckName": "4000 Essential English Words::1.Book"}
        order_map = {"4000 Essential English Words::1.Book::::agree": 1}
        cue_map = {"4000 Essential English Words::1.Book::::agree": "aynı fikirde olmak"}
        planned = {}

        def fake_apply_card_plan(deck_cards, active_cards, suspended_cards):
            planned["deck_cards"] = deck_cards
            planned["active_cards"] = active_cards
            planned["suspended_cards"] = suspended_cards

        def fake_invoke(action, **params):
            if action == "findNotes":
                return [1]
            if action == "notesInfo":
                return [note]
            if action == "cardsInfo":
                return [{"cardId": 201, "deckName": "4000 Essential English Words::1.Book"}]
            return []

        with patch.object(sync_4000_production_to_anki, "invoke", side_effect=fake_invoke), \
             patch.object(sync_4000_production_to_anki, "ENGLISH_MODELS", ("4000 EEW",)), \
             patch.object(sync_4000_production_to_anki, "update_note_fields_many"), \
             patch.object(sync_4000_production_to_anki, "get_notes", return_value=[note]), \
             patch.object(sync_4000_production_to_anki, "card_maps_for_notes", return_value={1: {0: 201, 1: 202}}), \
             patch.object(sync_4000_production_to_anki, "apply_card_plan", side_effect=fake_apply_card_plan):
            result = sync_4000_production_to_anki.sync_english(
                order_map, cue_map, active_limit=400, force=True
            )

        self.assertEqual(result["recognition_suspended"], 1)
        self.assertEqual(result["production_suspended"], 0)
        self.assertNotIn(201, planned["active_cards"])
        self.assertIn(201, planned["suspended_cards"])
        self.assertIn(202, planned["active_cards"])

    def test_duplicate_turkish_cues_keep_canonical_typed_answers(self):
        """Reviewed context disambiguates duplicate L1 cues without removing typing."""
        lower_key = "4000 Essential English Words::1.Book::::lower"
        drop_key = "4000 Essential English Words::1.Book::::drop"
        notes = [
            {
                "noteId": 1,
                "fields": {
                    "ProductionSourceID": {"value": lower_key},
                    "Word": {"value": "lower"},
                },
                "cards": [],
                "tags": [],
            },
            {
                "noteId": 2,
                "fields": {
                    "ProductionSourceID": {"value": drop_key},
                    "Word": {"value": "drop"},
                },
                "cards": [],
                "tags": [],
            },
        ]

        def fake_invoke(action, **params):
            if action == "findNotes":
                return [1, 2]
            if action == "notesInfo":
                return notes
            return []

        with patch.object(sync_4000_production_to_anki, "invoke", side_effect=fake_invoke), \
             patch.object(sync_4000_production_to_anki, "ENGLISH_MODELS", ("4000 EEW",)), \
             patch.object(sync_4000_production_to_anki, "update_note_fields_many") as mock_update, \
             patch.object(sync_4000_production_to_anki, "get_notes", return_value=notes), \
             patch.object(sync_4000_production_to_anki, "card_maps_for_notes", return_value={}), \
             patch.object(sync_4000_production_to_anki, "apply_card_plan"):
            sync_4000_production_to_anki.sync_english(
                {lower_key: 1, drop_key: 2},
                {lower_key: "düşürmek", drop_key: "düşürmek"},
                active_limit=400,
                force=True,
                sense_rows={
                    lower_key: {
                        "EnglishMeaning": "To lower something is to make it go down."
                    },
                    drop_key: {
                        "EnglishMeaning": "To drop is to let something fall."
                    },
                },
            )

        updates = dict(mock_update.call_args.args[0])
        self.assertEqual("lower", updates[1]["ProductionAnswer"])
        self.assertEqual("drop", updates[2]["ProductionAnswer"])
        self.assertIn(
            "{{type:ProductionAnswer}}",
            sync_4000_production_to_anki.ENGLISH_PRODUCTION_FRONT,
        )

    def test_locked_manual_cue_gets_missing_answer_without_overwrite(self):
        """Enabling typing on a protected note must not replace its custom cue."""
        key = "4000 Essential English Words::1.Book::::lower"
        note = {
            "noteId": 1,
            "fields": {
                "ProductionSourceID": {"value": key},
                "ProductionCue": {"value": "benim özel ipucum"},
                "ProductionAnswer": {"value": ""},
                "Word": {"value": "lower"},
            },
            "cards": [],
            "tags": [anki_protect.LOCKED_TAG],
        }

        def fake_invoke(action, **params):
            if action == "findNotes":
                return [1]
            if action == "notesInfo":
                return [note]
            return []

        with patch.object(sync_4000_production_to_anki, "invoke", side_effect=fake_invoke), \
             patch.object(sync_4000_production_to_anki, "ENGLISH_MODELS", ("4000 EEW",)), \
             patch.object(sync_4000_production_to_anki, "update_note_fields_many") as mock_update, \
             patch.object(sync_4000_production_to_anki, "get_notes", return_value=[note]), \
             patch.object(sync_4000_production_to_anki, "card_maps_for_notes", return_value={}), \
             patch.object(sync_4000_production_to_anki, "apply_card_plan"):
            result = sync_4000_production_to_anki.sync_english(
                {key: 1},
                {key: "düşürmek"},
                active_limit=400,
                sense_rows={
                    key: {
                        "EnglishMeaning": "To lower something is to make it go down."
                    }
                },
            )

        self.assertEqual(1, result["skipped_locked"])
        self.assertEqual(1, result["typing_enabled_locked"])
        mock_update.assert_called_once_with([(1, {"ProductionAnswer": "lower"})])

    def test_english_4000_legacy_generated_cue_migrates_without_locking(self):
        """The old plain production cue is recognized as generated on first sync."""
        key = "4000 Essential English Words::1.Book::::agree"
        level = sync_4000_production_to_anki.level_for_order(1)
        fields = {
            "Word": {"value": "agree"},
            "ProductionSourceID": {"value": key},
            "ProductionCue": {"value": "aynı fikirde olmak"},
            "ProductionAnswer": {"value": "agree"},
            "ProductionOrder": {"value": "1"},
            "ProductionLevel": {"value": level},
            "ProductionEnabled": {"value": "yes"},
        }
        note = {
            "noteId": 1,
            "fields": fields,
            "cards": [201, 202],
            "cardsInfoDeckName": "4000 Essential English Words::1.Book",
            "tags": [],
        }

        def fake_invoke(action, **params):
            if action == "findNotes":
                return [1]
            if action == "notesInfo":
                return [note]
            if action == "cardsInfo":
                return [{"cardId": 201, "deckName": note["cardsInfoDeckName"]}]
            return []

        with patch.object(sync_4000_production_to_anki, "invoke", side_effect=fake_invoke) as mock_invoke, \
             patch.object(sync_4000_production_to_anki, "ENGLISH_MODELS", ("4000 EEW",)), \
             patch.object(sync_4000_production_to_anki, "update_note_fields_many") as mock_update, \
             patch.object(sync_4000_production_to_anki, "get_notes", return_value=[note]), \
             patch.object(sync_4000_production_to_anki, "card_maps_for_notes", return_value={1: {}}), \
             patch.object(sync_4000_production_to_anki, "apply_card_plan"):
            result = sync_4000_production_to_anki.sync_english(
                {key: 1},
                {key: "aynı fikirde olmak"},
                active_limit=400,
                sense_rows={key: {"EnglishMeaning": "To agree is to have the same opinion."}},
            )

        self.assertEqual(1, result["updated_notes"])
        self.assertEqual(0, result["auto_locked"])
        mock_update.assert_called_once()
        self.assertNotIn("addTags", [call.args[0] for call in mock_invoke.call_args_list])

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
        """Test noun production cues include article and source-sense context."""
        fields = {
            "English": {"value": "backpack"},
            "Spanish": {"value": "la mochila"},
            "SpanishPartOfSpeech": {"value": "noun"},
            "EnglishMeaning": {"value": "A backpack is a bag carried on the back."},
        }
        cue = sync_4000_production_to_anki.spanish_production_cue(fields)
        self.assertEqual(sync_4000_production_to_anki.spanish_base_production_cue(fields), "the backpack")
        self.assertIn("the backpack", cue)
        self.assertIn("Context", cue)
        self.assertIn("A backpack is a bag", cue)
        self.assertIn("{{type:ProductionAnswer}}", sync_4000_production_to_anki.SPANISH_PRODUCTION_FRONT)
        self.assertNotIn("{{^ProductionAnswer}}", sync_4000_production_to_anki.SPANISH_PRODUCTION_FRONT)
        self.assertNotIn("{{Image}}", sync_4000_production_to_anki.SPANISH_PRODUCTION_FRONT)

    def test_english_production_cue_masks_answer_and_supports_self_grading(self):
        """Test Turkish prompts disambiguate the source sense without leaking English."""
        cue = sync_4000_production_to_anki.english_production_cue(
            "yeti / yetenek",
            "faculty",
            "A faculty is a mental or physical ability.",
            "Her faculties remained sharp.",
        )
        self.assertIn("yeti / yetenek", cue)
        self.assertIn("A _____ is a mental or physical ability.", cue)
        self.assertNotIn("A faculty is", cue)
        self.assertIn("Bağlam", cue)
        self.assertNotIn("{{^ProductionAnswer}}", sync_4000_production_to_anki.ENGLISH_PRODUCTION_FRONT)

    def test_card_templates_do_not_repeat_generic_answer_instructions(self):
        templates = (
            sync_4000_production_to_anki.SPANISH_PRODUCTION_FRONT,
            sync_4000_production_to_anki.SPANISH_PRODUCTION_BACK,
            sync_4000_production_to_anki.SPANISH_CONTEXT_PRODUCTION_FRONT,
            sync_4000_production_to_anki.ENGLISH_PRODUCTION_FRONT,
            sync_4000_production_to_anki.ENGLISH_PRODUCTION_BACK_MAIN,
            sync_4000_production_to_anki.ENGLISH_PRODUCTION_BACK_EXTRA,
            sync_english_mastery_to_anki.FRONT_TEMPLATE,
            sync_spanish_core_to_anki.FRONT_TEMPLATE,
        )
        redundant_phrases = (
            "source-deck answer",
            "Natural synonyms count",
            "Valid synonyms count",
            "then reveal and self-grade",
            "then compare carefully",
            "before showing the back",
            "Include the article for nouns",
        )
        rendered_templates = "\n".join(templates)
        self.assertNotIn("{{Level}} · {{CardType}}", rendered_templates)
        for phrase in redundant_phrases:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, rendered_templates)

    def test_english_production_cue_masks_inflections_and_uses_neutral_label(self):
        cases = [
            ("photograph", "I like taking photographs."),
            ("happen", "If that happens, call me."),
            ("comprise", "The collection comprises four books."),
            ("source", "Sources should be checked."),
            ("sense", "She senses danger."),
            ("have", "She has enough time."),
            ("context", "The context should disambiguate the word."),
        ]
        for answer, meaning in cases:
            with self.subTest(answer=answer):
                cue = sync_4000_production_to_anki.english_production_cue(
                    "Türkçe ipucu", answer, meaning
                )
                visible = sync_4000_production_to_anki.strip_html(cue).lower()
                self.assertIn("_____", visible)
                self.assertNotRegex(visible, rf"\b{re.escape(answer)}(?:s|es)?\b")
                self.assertNotIn("source sense", visible)
                self.assertIn("bağlam", visible)

    def test_turkish_cue_source_uses_reviewed_english(self):
        path = Path("generated/english_4000/english_turkish_production.tsv")
        rows = sync_4000_production_to_anki.load_turkish_rows(path)
        consist = next(row for row in rows.values() if row.get("English") == "consist")
        comprise = next(row for row in rows.values() if row.get("English") == "comprise")

        self.assertEqual(
            "To consist of things is to be made of those parts or things.",
            consist["EnglishMeaning"],
        )
        self.assertNotIn("certain", consist["EnglishMeaning"])
        self.assertIn("comprised of seniors", comprise["EnglishExample"])

    def test_spanish_verb_paradigms_are_latin_american_and_self_graded(self):
        """Test multi-form verb grids omit vosotros and avoid monolithic exact grading."""
        cards = spanish_core_learning.get_cards(card_type="verb_paradigm")
        multi_form = [card for card in cards if "|" in card["Answer"]]
        self.assertTrue(multi_form)
        for card in multi_form:
            self.assertEqual("self_grade", card["PromptMode"])
            self.assertEqual("", card["TypeAnswer"])
            self.assertNotIn("vosotros", card["Formula"])
            self.assertEqual(4, card["Answer"].count("|"))

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

    def test_spanish_production_limits_keep_context_cards_suspended(self):
        """Test Spanish 4000 normal production is active while context production is hidden."""
        self.assertGreaterEqual(sync_4000_production_to_anki.SPANISH_ACTIVE_LIMIT, 3871)
        self.assertEqual(0, sync_4000_production_to_anki.SPANISH_CONTEXT_ACTIVE_LIMIT)

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

    def test_marked_english_turkish_cues_are_disambiguated(self):
        """Test marked English 4000 cues include only necessary context for ambiguous words."""
        path = Path("generated/english_4000/english_turkish_production.tsv")
        if not path.exists():
            self.skipTest("English Turkish production TSV is not generated")

        expected = {
            "shake": "el sıkışmak / tokalaşmak",
            "profit": "kâr / kazanç",
            "dull": "sıkıcı / heyecansız",
            "former": "önceki / artık olmayan",
            "loan": "borç / kredi",
            "practical": "kullanışlı / yararlı / pratik",
            "available": "mevcut / müsait / kullanılabilir",
            "specific": "spesifik / belirli",
            "precise": "kesin / net",
            "explicit": "açık / net",
            "enroll": "kaydolmak",
        }
        rows = {}
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                rows.setdefault(row["English"].lower(), row)

        for english, cue in expected.items():
            self.assertEqual(cue, rows[english]["TurkishCue"].strip().lower())

    def test_live_reviewed_english_turkish_cues_are_preserved(self):
        """Test clearer Turkish cues reviewed in Anki are preserved in generated source."""
        path = Path("generated/english_4000/english_turkish_production.tsv")
        if not path.exists():
            self.skipTest("English Turkish production TSV is not generated")

        expected = {
            "clerk": "mağaza görevlisi / satış görevlisi",
            "locate": "yerini bulmak / konumunu tespit etmek",
            "earn": "para kazanmak",
            "safety": "güvenlik / sağlamlık",
            "perform": "sahnelemek / icra etmek",
            "strike": "saldırmak / vurmak",
            "term": "terim / sözcük",
            "recognize": "tanımak / hatırlamak",
            "along": "birlikte / yanında",
            "attract": "cezbetmek / ilgisini çekmek",
            "maintain": "sürdürmek / düzenli bakmak",
            "neither": "hiçbiri / ne o ne bu",
            "situated": "yer almak / bulunmak",
            "false": "yanlış / sahte",
            "figure out": "çözmek / anlamak",
            "rather": "daha doğrusu / tercihen",
            "such": "böyle / radde / bu derece",
            "essential": "önemli / temel şey",
            "immediate": "hemen / anlık",
            "pace": "sürat",
            "battle": "savaş / çatışma",
            "military": "ordu",
            "twist": "bükmek / ekseninde döndürmek",
            "unless": "... sürece",
            "confidence": "güven / özgüven",
            "consequence": "sonuç",
            "pale": "soluk / solgun",
            "supplement": "destekleyici gıda / madde",
            "band": "müzik grubu / bant",
            "barely": "zar zor / anca",
            "schedule": "program / takvim",
            "burden": "yük / sorumluluk",
            "compromise": "ödün vermek / uzlaşmak",
            "meeting": "toplantı / buluşma",
            "moderate": "ılımlı / ne az ne fazla",
            "settle": "uzlaşmak / sonuca erdirmek",
            "demonstrate": "göstermek / sunmak",
        }
        rows = {}
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                rows[row["English"].lower()] = row

        for english, cue in expected.items():
            self.assertEqual(cue, rows[english]["TurkishCue"].strip().lower())

    def test_english_turkish_cues_fix_high_confidence_wrong_senses(self):
        """Test Turkish cues do not keep common wrong-sense machine translations."""
        path = Path("generated/english_4000/english_turkish_production.tsv")
        if not path.exists():
            self.skipTest("English Turkish production TSV is not generated")

        expected = {
            "december": "Aralık ayı",
            "plate": "tabak",
            "pole": "direk / sırık",
            "tip": "uç",
            "medicine": "ilaç",
            "mix": "karışım",
            "populate": "yaşamak / yerleşmek",
            "dive": "dalmak",
            "household": "hane / ev halkı",
            "log": "kütük",
            "destination": "varış noktası / hedef",
            "consume": "tüketmek / yiyip içmek",
            "exhaust": "yormak / bitkin düşürmek",
            "study": "ders çalışmak / incelemek",
            "work": "çalışmak / iş yapmak",
            "site": "yer / alan",
            "terminal": "ölümcül / son evre",
            "subject": "maruz bırakmak / tabi tutmak",
            "opossum": "keseli sıçan",
            "dna": "DNA",
            "consist": "parçalardan oluşmak / -den oluşmak",
            "comprise": "içermek / -den oluşmak",
            "poor": "kötü / yetersiz",
            "destruction": "yıkım / tahribat",
            "platform": "platform / mecra",
            "presence": "varlık / bulunma",
            "equipment": "ekipman / donanım",
            "stroll": "ağır ağır yürümek / dolaşmak",
            "depend": "dayanmak / ihtiyaç duymak",
            "actual": "gerçek / asıl / gerçeğe dayalı",
            "base": "taban / alt kısım",
            "organize": "düzenlemek / organize etmek",
            "cost": "mal olmak / tutmak",
            "consequence": "sonuç",
            "incredible": "inanılmaz / olağanüstü",
            "can": "-ebilmek / yapabilmek",
            "clear": "boşaltmak / temizlemek",
            "depart": "ayrılmak / yola çıkmak",
            "nevertheless": "yine de / buna rağmen",
            "ruins": "harabeler / kalıntılar",
            "significant": "önemli / kayda değer",
            "capable": "yetenekli / yapabilecek durumda",
            "convey": "iletmek / aktarmak",
            "delight": "sevinç / mutluluk",
            "against": "-e karşı / -e yaslanmış",
            "prevent": "önlemek",
            "enormous": "devasa / çok büyük",
            "extraordinary": "olağanüstü / sıra dışı",
            "mad": "öfkeli / kızgın",
            "trap": "tuzağa düşürmek / yakalamak",
            "trial": "yargılama / dava",
            "admission": "giriş izni / kabul",
            "forecast": "hava tahmini",
            "afford": "parası yetmek / karşılayabilmek",
            "mess": "dağınıklık",
            "fortune": "talih",
            "engineer": "tasarlamak / ustaca planlamak",
            "kid": "şaka yapmak",
            "disguise": "kılık / kılık değiştirme",
            "puff": "bir tutam / duman bulutu",
            "stem": "gövde / sap",
            "howl": "ulumak",
            "peer": "dikkatle bakmak",
            "consequent": "sonuç olarak ortaya çıkan",
            "curve": "kavis çizmek / eğrilmek",
            "practice": "alışkanlık / uygulama",
            "verify": "doğrulamak / teyit etmek",
            "render": "hâle getirmek",
            "upgrade": "geliştirmek / yükseltmek",
            "utensil": "mutfak gereci / araç",
            "crisp": "çıtır / gevrek",
            "review": "inceleme / değerlendirme",
            "nick": "hafifçe kesmek / çizmek",
            "orbit": "yörüngede dönmek",
            "tract": "geniş arazi / bölge",
            "amend": "düzeltmek / iyileştirmek",
        }
        forbidden = {
            "plate": "plaka",
            "pole": "kutup",
            "medicine": "tıp",
            "mix": "karıştır",
            "populate": "nüfuslu",
            "dive": "dalış",
            "household": "ev",
            "log": "günlük",
            "base": "baz",
            "fortune": "servet",
            "mad": "deli",
            "trial": "deneme",
            "afford": "göze almak",
            "engineer": "mühendisliğe",
            "kid": "çocuğa",
            "stem": "kök",
            "peer": "akran",
            "crisp": "net",
            "tract": "yol",
        }
        rows = {}
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                rows[row["English"].lower()] = row

        for english, cue in expected.items():
            self.assertEqual(cue.lower(), rows[english]["TurkishCue"].strip().lower())
        for english, bad_cue in forbidden.items():
            self.assertNotEqual(bad_cue, rows[english]["TurkishCue"].strip().lower())

    def test_english_turkish_cue_audit_has_no_machine_artifacts(self):
        """Test all durable Turkish cues are complete and free of known machine debris."""
        path = Path("generated/english_4000/english_turkish_production.tsv")
        bad_rows = []
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                cue = row["TurkishCue"].strip()
                if (
                    not cue
                    or row["Status"].startswith(("error", "pending"))
                    or any(marker in cue for marker in ("<", ">", "&nbsp;", "Ã", "Â", "�", "EOF", "\u00a0"))
                    or re.search(r"\biçin$", cue, re.IGNORECASE)
                    or re.search(r"'[ae]$", cue, re.IGNORECASE)
                ):
                    bad_rows.append((row["SourceID"], cue, row["Status"]))

        self.assertEqual([], bad_rows[:20])

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
            "un premio es un premio",
            "algo grande es muy grande",
            "un sabor es el sabor",
            "un hilo es un trozo fino de hilo",
            "muy brillante o inteligente",
            "muy elegante y agradable",
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
            "Cue: do",
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
