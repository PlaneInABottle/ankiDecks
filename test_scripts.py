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
import spanish_deck
import sync_4000_production_to_anki
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


    def test_spanish_pronunciation_hint_examples(self):
        """Test readable Latin American Spanish pronunciation hints."""
        examples = {
            "año": "A-nyo",
            "mochila": "mo-Çİ-la",
            "cinturón": "sin-tu-RON",
            "queso": "KE-so",
            "guitarra": "gi-TAR-ra",
            "llave": "YA-be",
            "orgulloso": "or-gu-YO-so",
            "collar": "ko-YAR",
            "jardín": "har-DİN",
            "círculo": "SİR-ku-lo",
            "tía": "Tİ-a",
            "país": "pa-İS",
            "teatro": "te-A-tro",
            "hoy": "Oİ",
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

        pronominal = spanish_deck.infer_spanish_metadata("apagarse")
        self.assertEqual("pronominal verb", pronominal["spanish_part_of_speech"])
        self.assertIn("infinitive: apagarse", pronominal["spanish_forms"])
        self.assertIn("pronouns: me, te, se, nos, se", pronominal["spanish_forms"])

        accented_infinitive = spanish_deck.infer_spanish_metadata("sonreír")
        self.assertEqual("verb", accented_infinitive["spanish_part_of_speech"])
        self.assertIn("infinitive: sonreír", accented_infinitive["spanish_forms"])
        self.assertIn("-ir pattern", accented_infinitive["spanish_forms"])

        sea_urchin = spanish_deck.infer_spanish_metadata("el erizo de mar")
        self.assertEqual("masculine", sea_urchin["spanish_gender"])
        self.assertEqual(
            "singular: el erizo de mar; plural: los erizos de mar",
            sea_urchin["spanish_forms"],
        )

        for stressed_a_noun, plural in {
            "el área": "las áreas",
            "el hacha": "las hachas",
            "el alma": "las almas",
            "el arma": "las armas",
        }.items():
            metadata = spanish_deck.infer_spanish_metadata(stressed_a_noun)
            self.assertEqual("feminine", metadata["spanish_gender"])
            self.assertIn(f"plural: {plural}", metadata["spanish_forms"])

        for noun, plural in {
            "el país": "los países",
            "el autobús": "los autobuses",
            "el mes": "los meses",
        }.items():
            self.assertIn(
                f"plural: {plural}",
                spanish_deck.infer_spanish_metadata(noun)["spanish_forms"],
            )

        sunglasses = spanish_deck.infer_spanish_metadata("las gafas de sol")
        self.assertEqual("noun", sunglasses["spanish_part_of_speech"])
        self.assertEqual("", sunglasses["spanish_forms"])

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

    def test_spanish_reviewed_glossary_rejects_known_invalid_content(self):
        """Test reviewed status cannot bypass deterministic content validation."""
        self.assertEqual(
            ["invalid Spanish token(s): romer, rompio"],
            spanish_deck.reviewed_glossary_errors(
                {
                    "spanish": "romer",
                    "spanish_meaning": "Romer significa romper algo.",
                    "spanish_example": "Jacob rompio la ventana.",
                }
            ),
        )
        self.assertEqual(
            [],
            spanish_deck.reviewed_glossary_errors(
                {
                    "spanish": "romper",
                    "spanish_meaning": "Romper significa hacer que algo se quiebre.",
                    "spanish_example": "Jacob rompió la ventana.",
                }
            ),
        )
        self.assertEqual(
            ["invalid Spanish token(s): bilíngüe, móvilizar"],
            spanish_deck.reviewed_glossary_errors(
                {
                    "spanish": "bilíngüe",
                    "spanish_meaning": "La forma móvilizar tampoco es válida.",
                    "spanish_example": "El texto contiene errores conocidos.",
                }
            ),
        )
        # This is a valid unaccented verb form, so the regression list must not
        # grow into a context-free Spanish spellchecker.
        self.assertEqual(
            [],
            spanish_deck.reviewed_glossary_errors(
                {
                    "spanish": "ejercitar",
                    "spanish_meaning": "Yo ejercito los brazos.",
                    "spanish_example": "Ejercito los brazos cada mañana.",
                }
            ),
        )

    def test_spanish_reviewed_glossary_content_fixes_stay_aligned(self):
        """Test corrected headwords and examples preserve their source sense."""
        glossary_path = Path("generated/spanish_reviewed_glossary_full.tsv")
        with glossary_path.open(encoding="utf-8", newline="") as handle:
            rows = {row["english"]: row for row in csv.DictReader(handle, delimiter="\t")}

        self.assertEqual("el erizo de mar", rows["sea urchin"]["spanish"])
        self.assertEqual("romper", rows["smash"]["spanish"])
        self.assertIn("rompió", rows["smash"]["spanish_example"])
        self.assertEqual("apagarse", rows["stall"]["spanish"])
        self.assertIn("motor", rows["stall"]["spanish_meaning"])
        self.assertIn("él les dio dinero", rows["corrupt"]["spanish_example"])
        self.assertIn("suricatos", rows["upright"]["spanish_example"])
        self.assertEqual("encantar", rows["charm"]["spanish"])
        self.assertEqual("unir", rows["bind"]["spanish"])
        self.assertEqual("principal", rows["primary"]["spanish"])
        self.assertIn("lo más importante", rows["primary"]["spanish_meaning"])
        self.assertEqual("orgulloso", rows["proud"]["spanish"])

        expected_targets = {
            "admission": "la entrada",
            "basis": "la base",
            "casual": "informal",
            "couple": "un par",
            "disseminate": "difundir",
            "dive": "zambullirse",
            "extension": "la ampliación",
            "ferry": "el transbordador",
            "instance": "un caso",
            "jealousy": "la envidia",
            "management": "el manejo",
            "moral": "la moraleja",
            "neither": "ni... ni...",
            "nausea": "las náuseas",
            "overwork": "sobrecargar de trabajo",
            "scrap": "el recorte",
            "shallow": "poco profundo",
            "valentine": "la pareja de San Valentín",
            "virtual": "de facto",
            "vocal": "expresar abiertamente",
            "wild": "silvestre",
            "worthwhile": "valer la pena",
        }
        for english, spanish in expected_targets.items():
            self.assertEqual(spanish, rows[english]["spanish"])

        for row in rows.values():
            self.assertEqual([], spanish_deck.reviewed_glossary_errors(row), row["english"])

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
            "Las mangostas son frutas",
            "fuente autoritaria",
            "no se pagar",
            "panadero tamizo",
            "Sé algo ignorante",
            "gérmenes finos",
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
            "along": "boyunca",
            "attract": "cezbetmek / ilgisini çekmek",
            "maintain": "sürdürmek / düzenli bakmak",
            "neither": "hiçbiri / ne o ne bu",
            "situated": "yer almak / bulunmak",
            "false": "yanlış / sahte",
            "figure out": "çözmek / anlamak",
            "rather": "daha doğrusu / tercihen",
            "such": "böyle / radde / bu derece",
            "essential": "önemli / temel",
            "immediate": "hemen / anlık",
            "pace": "sürat",
            "battle": "savaş / çatışma",
            "military": "ordu",
            "twist": "bükmek / ekseninde döndürmek",
            "unless": "... sürece",
            "confidence": "güven / özgüven",
            "consequence": "sonuç",
            "pale": "soluk / solgun",
            "supplement": "takviye etmek / gıda takviyesi",
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
            "subject": "konu / maruz bırakmak",
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
        "glory": "şan / görkem",
            "engineer": "tasarlamak / ustaca planlamak",
            "kid": "çocuk / şaka yapmak",
            "disguise": "kılık / kılık değiştirme",
            "puff": "bir tutam / duman bulutu",
            "stem": "gövde / sap",
            "howl": "ulumak",
            "peer": "akran / dikkatle bakmak",
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
            # Manual sense fixes from the 2026-09-10 audit (bare-word machine
            # output had picked the wrong sense or wrong POS form).
            "coin": "türetmek / yeni sözcük üretmek",
            "branch": "dal",
            "pity": "acıma",
            "straightforward": "açık sözlü / anlaşılır",
            "vocal": "fikrini açıkça dile getiren",
            "leading": "öncü / lider",
            "bacon": "domuz pastırması",
            "imperial": "imparatorlukla ilgili",
            "upcoming": "yaklaşan",
            "bankrupt": "iflas etmiş / müflis",
            "bench": "bank",
            "abandon": "terk etmek",
            "aboard": "gemide / uçakta",
            "absence": "yokluk",
            "accommodate": "yer sağlamak / barındırmak",
            "aerial": "havadan",
            "affair": "hâdise",
            "albeit": "-e rağmen",
            "align": "yanında yer almak / desteklemek",
            "alligator, crocodile": "aligatör / timsah",
            "ample": "kâfi",
            "animate": "yaşayan",
            "aquatic": "suda yaşayan",
            "armed": "silahlı",
            "artery": "atardamar",
            "artifact": "tarihi eser",
            "ashamed": "utanmış",
            "ashore": "karaya",
            "aspect": "boyut",
            "assembly": "meclis",
            "asset": "katma değer",
            "assign": "görev dağıtmak",
            "assure": "güvence vermek",
            "aunt": "teyze / hala",
            "avail": "yarar / fayda",
            "bargain": "kelepir",
            "basin": "leğen",
            "bead": "damla",
            "beloved": "çok sevilen",
            "bend": "bükmek",
            "bind": "kenetlemek",
            "bite": "ısırma",
            "bitter": "kırgın",
            "bliss": "saadet",
            "brute": "kaba saba kimse",
            "bulk": "büyük bölüm / hacim",
            "bury": "gömmek",
            "buzz": "heyecan yaratmak",
            "cabin": "kütük ev",
            "calf": "baldır",
            "cap": "kep",
            "caretaker": "bakıcı",
            "carriage": "fayton",
            "cast": "fırlatmak",
            "cater": "ihtiyaçları karşılamak",
            "celebrity": "ünlü kişi",
            "charter": "kiralamak / berat",
            "cheer": "tezahürat yapmak / neşelendirmek",
            "chef": "aşçı",
            "chill": "ürperti",
            "choke": "boğazına kaçmak",
            "civic": "yurttaşlıkla ilgili",
            "cliff": "yar",
            "coat": "palto",
            "commission": "görevlendirmek",
            "complain": "şikayet etmek",
            "compose": "parçalardan birleştirmek",
            "compound": "bileşik / kapalı yerleşke",
            "conceive": "tasavvur etmek",
            "condensed": "yoğunlaştırılmış",
            "connect": "bağlantı kurmak",
            "consolidate": "birleştirip sağlamlaştırmak",
            "contingent": "heyet / birlik",
            "convention": "görenek",
            "corrupt": "yolsuz",
            "cot": "portatif yatak",
            "cottage": "kır evi",
            "counterpart": "muadil",
            "cram": "tıkıştırmak",
            "creation": "eser",
            "decent": "makul",
            "decorate": "süslemek / dekore etmek",
            "deduct": "kesinti yapmak",
            "deposit": "para yatırmak",
            "dine": "akşam yemeği yemek",
            "dip": "düşüş",
            "disabled": "engelli",
            "discharge": "taburcu etmek",
            "dish": "yemek çeşidi",
            "dismiss": "önemsememek / geçiştirmek",
            "display": "teşhir etmek",
            "dissatisfy": "memnun edememek",
            "dissolve": "eritmek",
            "domestic": "ülke içi",
            "doomed": "mahvolmaya mahkum",
            "downtown": "şehir merkezi",
            "drain": "gider borusu",
            "due": "vadesi gelmiş",
            "dumb": "dilsiz",
            "earthen": "topraktan",
            "element": "unsur",
            "enable": "olanak sağlamak",
            "engage": "uğraşmak / girişmek",
            "entire": "bütün",
            "entitle": "hak vermek",
            "epic": "destan",
            "escape": "kaçıp kurtulmak",
            "escort": "refakat etmek",
            "execute": "idam etmek",
            "expel": "kovmak / çıkarmak",
            "extension": "ek / uzantı",
            "extinct": "nesli tükenmiş",
            "fantastic": "fevkalade",
            "fat": "katı yağ",
            "father, dad": "baba",
            "feat": "büyük başarı",
            "flush": "kızarmak",
            "forthcoming": "gelmekte olan",
            "foster": "geliştirmek / desteklemek",
            "foul": "pis",
            "frantic": "paniklemiş",
            "from": "-den / -dan",
            "fuse": "fitil",
            "garment": "giyecek",
            "gaze": "dik dik bakmak",
            "glance": "göz atmak",
            "glimpse": "gözüne ilişmek",
            "grand": "görkemli / büyük",
            "grandfather, grandpa": "büyükbaba",
            "grandmother, grandma": "büyükanne",
            "grim": "ürkütücü",
            "gulf": "görüş ayrılığı",
            "guts": "iç organlar",
            "hack": "parçalayarak doğramak",
            "hesitant": "tereddütlü",
            "hold": "tutmak / haiz olmak",
            "horn": "korna",
            "horrified": "şoke olmuş",
            "hostile": "düşmanca",
            "humor": "mizah",
            "idle": "aylak / boş",
            "impending": "olmak üzere olan",
            "individual": "birey",
            "infamous": "kötü nam salmış",
            "inferior": "kalitesiz",
            "ingenious": "dahiyane",
            "inhabitant": "mukim",
            "inhibit": "ket vurmak",
            "initial": "ilk",
            "inland": "iç kesim",
            "instrument": "alet",
            "intake": "alım",
            "integrity": "doğruluk",
            "intelligence": "zeka",
            "interchange": "fikir alışverişi",
            "interpret": "yorumlamak",
            "invoke": "ileri sürmek / dayanak göstermek",
            "january": "Ocak",
            "jaw": "çene kemiği",
            "junior": "kıdemsiz",
            "keen": "hevesli / zeki",
            "keep": "saklamak / devam ettirmek",
            "key": "kilit",
            "kit": "set",
            "known": "bilinen",
            "landmark": "nirengi noktası",
            "law": "kanun / yasa",
            "lay": "yatırmak",
            "liable": "olası / muhtemel",
            "limb": "kalın dal",
            "locale": "mekan",
            "lunar": "aya ait",
            "majesty": "ululuk",
            "major": "büyük / önemli",
            "mandarin": "mandarin çincesi",
            "mark": "işaretlemek / kutlamak",
            "marshal": "toplayıp düzene sokmak",
            "martial": "savaşla ilgili",
            "massive": "iri / kocaman",
            "meantime": "aradaki süre",
            "medieval": "ortaçağa ait",
            "mercy": "merhamet",
            "metal": "metal",
            "metropolitan": "büyükşehre ait",
            "midst": "tam ortası",
            "might": "kudret",
            "mineral": "mineral",
            "misguided": "yanlış yönlendirilmiş",
            "mittens": "tek parmaklı eldiven",
            "mob": "güruh",
            "moral": "ahlak dersi",
            "mother, mom": "anne",
            "municipal": "belediyeye ait",
            "my parents' nephew": "anne babamın erkek yeğeni",
            "my parents' niece": "anne babamın kız yeğeni",
            "naval": "donanmayla ilgili",
            "navigate": "yön bulmak",
            "nurture": "besleyip büyütmek",
            "nut": "kuruyemiş",
            "occupy": "oturmak / işgal etmek",
            "officer": "subay",
            "omit": "dışarıda bırakmak",
            "ongoing": "devam eden",
            "operate": "çalışmak / işlemek",
            "oppress": "zulmetmek / baskı yapmak",
            "oracle": "kâhin",
            "oriented": "yönelmiş",
            "ought": "-meli / -malı",
            "outlook": "bakış açısı",
            "outraged": "çok öfkeli",
            "outright": "düpedüz",
            "outstretched": "uzatılmış",
            "overboard": "denize düşmüş",
            "overhead": "tepede",
            "overjoyed": "çok sevinmiş",
            "overnight": "bir gecede",
            "overwork": "fazla çalıştırmak",
            "paste": "macun",
            "persistent": "azimli / ısrarcı",
            "pioneer": "çığır açan",
            "plea": "yalvarış",
            "pledge": "söz vermek",
            "pot": "tencere",
            "practitioner": "hekim",
            "preliminary": "ön",
            "prevail": "kabul görmek / yaygın olmak",
            "prior": "evvelki",
            "prominent": "tanınmış",
            "promote": "terfi ettirmek / tanıtmak",
            "prompt": "sevk etmek",
            "prospect": "beklenti / olasılık",
            "provision": "sağlama / tedarik",
            "psychic": "medyum",
            "recycle": "geri dönüştürmek",
            "refine": "iyileştirmek",
            "register": "kayıt / sicil",
            "relief": "rahatlama",
            "repetitive": "tekrarlı",
            "reproductive": "üremeye ait",
            "resent": "gücenmek / içerlemek",
            "resolution": "karar",
            "respective": "her birine ait",
            "restore": "eski haline getirmek",
            "rid": "arındırmak",
            "ring": "yüzük",
            "robin": "kızılgerdan",
            "royal": "kraliyete ait",
            "sake": "hatır",
            "saturate": "tamamen ıslatmak",
            "save": "kurtarmak",
            "scheme": "plan / tertip",
            "scramble": "didinmek",
            "scrap": "kağıt parçası",
            "scribe": "katip",
            "seclude": "tecrit etmek",
            "select": "özenle seçmek",
            "set": "koymak",
            "shaft": "uzun sap",
            "shed": "baraka",
            "sheer": "tam / mutlak",
            "sheet": "tabaka",
            "shutter": "panjur",
            "sideways": "yanlamasına",
            "signify": "simgelemek",
            "silly": "ciddiyetsiz",
            "skeletal": "iskelete ait",
            "skiing": "kayak",
            "skill": "beceri",
            "sleeve": "yen",
            "sneak": "gizlice sokulmak",
            "snowboarding": "snowboard",
            "soar": "hızla yükselmek",
            "sob": "hıçkırarak ağlamak",
            "sober": "ağırbaşlı",
            "solar": "güneşle ilgili",
            "sole": "yegane",
            "sort": "çeşit / tür",
            "sow": "tohum ekmek",
            "space": "boş alan",
            "spare": "ihtiyaç fazlasını vermek",
            "species": "canlı türü",
            "speculate": "tahmin yürütmek",
            "stable": "sabit",
            "stall": "oyalamak",
            "still": "hâlâ",
            "stool": "tabure",
            "stranded": "mahsur kalmış",
            "straw": "pipet",
            "stray": "yolunu şaşırmak",
            "stricken": "yakalanmış / tutulmuş",
            "string": "ip",
            "stroke": "fırça darbesi",
            "stuffed": "doldurulmuş",
            "subscribe": "benimsemek / katılmak",
            "succession": "ardıllık",
            "sweatshirt": "sweatshirt",
            "swing": "sallamak",
            "sympathy": "şefkat",
            "tease": "dalga geçmek",
            "temper": "mizaç / huy",
            "tender": "yumuşak",
            "terror": "dehşet",
            "testament": "gösterge",
            "theorize": "kuram geliştirmek",
            "though": "olsa da",
            "tissue": "kağıt mendil",
            "tornado": "hortum",
            "transplant": "nakil",
            "tribute": "hürmet / saygı",
            "twig": "ince dal",
            "typewritten": "daktiloyla yazılmış",
            "uncle": "amca / dayı",
            "undergraduate": "lisans öğrencisi",
            "urban": "kentsel",
            "utility": "kamu hizmeti",
            "vain": "kendini beğenmiş",
            "valentine": "sevgili",
            "vessel": "gemi",
            "veteran": "deneyimli",
            "viable": "gerçekleşebilir",
            "vision": "görme",
            "volume": "toplam hacim",
            "wagon": "yük arabası",
            "whereabouts": "bulunduğu yer",
            "whereby": "vasıtasıyla",
            "wild": "yabani",
            "winding": "kıvrımlı",
            "yard": "ev bahçesi",
            "yield": "devretmek",
            "zip": "fermuar çekmek",
            "zoom": "hızla hareket etmek",
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
            "glory": "zafer",
            "trial": "deneme",
            "afford": "göze almak",
            "engineer": "mühendisliğe",
            "kid": "çocuğa",
            "stem": "kök",
            "peer": "akran",
            "crisp": "net",
            "tract": "yol",
            # Old wrong-sense outputs replaced by the 2026-09-10 audit.
            "coin": "madeni paraya çevirmek",
            "branch": "şube",
            "pity": "yazık",
            "straightforward": "açık sözlü",
            "vocal": "vokal",
            "leading": "liderlik etmek",
            "bacon": "pastırma",
            "imperial": "imparatorluk",
            "upcoming": "yakında",
            "bankrupt": "iflas etmek",
            "bench": "tezgah",
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
            ("4000 Essential English Words::Extra", "2_7", "cap"): "kep",
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
