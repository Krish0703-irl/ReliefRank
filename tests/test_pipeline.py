"""
Pipeline + store tests. The Gemma call is replaced by a fixed function here
so the tests run offline in a second. Ctrl+F5 this file (or run pytest).
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from reliefrank import pipeline, store

ANSWERS = {
    "roof": {"people_count": 4, "vulnerable": ["infant"], "trapped": True,
             "water_level": "chest", "location_text": "near St Mary church Aluva",
             "phone": "9876543210", "confidence": {"location": 0.9},
             "gemma_note": "4 people trapped on roof with infant"},
    "insulin": {"people_count": 2, "vulnerable": ["elderly"], "medical_need": True,
                "water_level": "knee", "location_text": None, "phone": None,
                "gemma_note": "elderly woman needs insulin"},
    "guess": {"people_count": 1, "location_text": "Ernakulam North",
              "phone": "9000000000"},
}


def fixed_extract(text, pack=None):
    for key, ans in ANSWERS.items():
        if key in text.lower():
            return dict(ans)
    return {}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_dir = config.DB_PATH, config.DATA_DIR
        config.DATA_DIR = Path(self.tmp.name)
        config.DB_PATH = config.DATA_DIR / "test.db"
        self.old_extract = pipeline.run_extract
        pipeline.run_extract = fixed_extract
        self.old_validate = pipeline._validate_mod
        pipeline._validate_mod = None          # test the built-in checks
        store.init_db()

    def tearDown(self):
        pipeline.run_extract = self.old_extract
        pipeline._validate_mod = self.old_validate
        config.DB_PATH, config.DATA_DIR = self.old_db, self.old_dir
        self.tmp.cleanup()

    def test_message_becomes_scored_case(self):
        c = pipeline.process_message(
            "Help! roof, water till chest, baby with us, near St Mary church Aluva, 9876543210")
        self.assertGreater(c.score, 50)
        self.assertFalse(c.needs_call)
        self.assertEqual(store.get_case(c.case_id).score, c.score)

    def test_missing_contact_goes_to_needs_call(self):
        c = pipeline.process_message("grandma needs insulin, water at knee")
        self.assertTrue(c.needs_call)
        self.assertIn("location", c.missing)
        self.assertIn("phone", c.missing)
        self.assertEqual([x.case_id for x in store.list_cases("needs call")], [c.case_id])

    def test_values_not_in_message_are_rejected(self):
        c = pipeline.process_message("guess: one person alone, please come")
        self.assertIsNone(c.location_text)
        self.assertIsNone(c.phone)
        self.assertTrue(c.needs_call)

    def test_same_phone_merges_into_one_case(self):
        a = pipeline.process_message("roof near St Mary church Aluva call 9876543210")
        b = pipeline.process_message("roof again!! still waiting St Mary church Aluva 98765 43210")
        self.assertEqual(a.case_id, b.case_id)
        self.assertEqual(len(store.list_cases()), 1)
        self.assertEqual(len(store.get_case(a.case_id).message_ids), 2)

    def test_model_failure_keeps_message(self):
        def broken(text, pack=None):
            raise ValueError("bad JSON")
        pipeline.run_extract = broken
        c = pipeline.process_message("anything at all")
        self.assertTrue(c.needs_call)
        self.assertIn("Could not read", c.gemma_note)

    def test_batch_skips_blank_lines_and_ranks(self):
        pipeline.process_batch(["grandma needs insulin", "",
                                "roof St Mary church Aluva 9876543210"])
        cases = store.list_cases()
        self.assertEqual(len(cases), 2)
        self.assertGreaterEqual(cases[0].score, cases[1].score)

    def test_update_status(self):
        c = pipeline.process_message("roof St Mary church Aluva 9876543210")
        store.update_status(c.case_id, "assigned")
        self.assertEqual(store.get_case(c.case_id).status, "assigned")
        self.assertEqual(store.list_cases("assigned")[0].case_id, c.case_id)

    def test_empty_message_rejected(self):
        with self.assertRaises(ValueError):
            pipeline.process_message("   ")


if __name__ == "__main__":
    unittest.main(verbosity=2)
