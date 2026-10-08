"""Dedupe tests. Ctrl+F5 this file (or run pytest)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reliefrank.dedupe import normalize_phone, find_duplicate, merge, text_similarity
from reliefrank.models import Case


def make(cid, text, phone=None, t="2026-10-08T12:00:00", **kw):
    return Case(cid, ["m_" + cid], [text], t, phone=phone, **kw)


class DedupeTests(unittest.TestCase):
    def test_normalize_phone(self):
        self.assertEqual(normalize_phone("+91 98765-43210"), "9876543210")
        self.assertEqual(normalize_phone("098765 43210"), "9876543210")
        self.assertEqual(normalize_phone("12345"), "")
        self.assertEqual(normalize_phone(None), "")

    def test_same_phone_matches(self):
        old = make("a", "help 4 people on roof", phone="9876543210")
        new = make("b", "totally different words", phone="+91 98765 43210")
        self.assertIs(find_duplicate(new, [old]), old)

    def test_different_phone_never_merges(self):
        old = make("a", "water at chest near temple road", phone="9876543210")
        new = make("b", "water at chest near temple road", phone="9123456789")
        self.assertIsNone(find_duplicate(new, [old]))

    def test_similar_text_matches(self):
        old = make("a", "Please help! 4 people stuck on roof near St Mary church Aluva")
        new = make("b", "please help 4 people stuck on the roof near st mary church aluva")
        self.assertIs(find_duplicate(new, [old]), old)

    def test_unrelated_text_does_not_match(self):
        old = make("a", "grandmother needs insulin, water at knee, Kalady")
        new = make("b", "family of six trapped on second floor Chalakudy")
        self.assertIsNone(find_duplicate(new, [old]))
        self.assertLess(text_similarity(old.raw_texts[0], new.raw_texts[0]), 0.8)

    def test_merge_keeps_most_urgent_and_earliest(self):
        base = make("a", "first", t="2026-10-08T12:00:00", water_level="knee",
                    people_count=2, vulnerable=["elderly"])
        new = make("b", "second", phone="9876543210", t="2026-10-08T12:30:00",
                   water_level="chest", people_count=4, vulnerable=["infant"], trapped=True)
        out = merge(base, new)
        self.assertEqual(out.case_id, "a")
        self.assertEqual(out.message_ids, ["m_a", "m_b"])
        self.assertEqual(out.received_at, "2026-10-08T12:00:00")
        self.assertEqual(out.water_level, "chest")
        self.assertEqual(out.people_count, 4)
        self.assertEqual(out.vulnerable, ["elderly", "infant"])
        self.assertTrue(out.trapped)
        self.assertEqual(out.phone, "9876543210")

    def test_merge_same_message_twice_is_ignored(self):
        base = make("a", "hello")
        merge(base, make("a", "hello"))
        self.assertEqual(len(base.message_ids), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
