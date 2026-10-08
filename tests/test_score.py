"""Scoring rule tests. Ctrl+F5 this file (or run pytest)."""
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reliefrank.models import Case
from reliefrank.score import score_case, apply_score, rank, reasons_line

NOW = datetime(2026, 10, 8, 13, 0)


def make(cid="c", mids=("m",), t="2026-10-08T13:00:00", **kw):
    return Case(cid, list(mids), ["x"] * len(mids), t, **kw)


class ScoreTests(unittest.TestCase):
    def test_example_from_plan_is_67(self):
        c = make(t="2026-10-08T12:20:00", people_count=4, vulnerable=["infant"],
                 trapped=True, water_level="chest")
        score, reasons = score_case(c, NOW)
        self.assertEqual(score, 67)
        self.assertIn("trapped +25", reasons)
        self.assertIn("water at chest +20", reasons)

    def test_empty_case_scores_zero(self):
        self.assertEqual(score_case(make(), NOW)[0], 0)

    def test_score_is_capped_at_100(self):
        c = make(mids=("a", "b"), t="2026-10-08T08:00:00", people_count=20, trapped=True,
                 water_level="roof", medical_need=True,
                 vulnerable=["infant", "elderly", "pregnant", "ill"])
        self.assertEqual(score_case(c, NOW)[0], 100)

    def test_vulnerable_and_people_caps(self):
        c = make(people_count=50, vulnerable=["infant", "elderly", "pregnant", "ill", "child"])
        _, reasons = score_case(c, NOW)
        self.assertIn("50 people +10", reasons)
        self.assertTrue(any(r.endswith("+30") for r in reasons))

    def test_waist_scores_less_than_chest(self):
        self.assertLess(score_case(make(water_level="waist"), NOW)[0],
                        score_case(make(water_level="chest"), NOW)[0])

    def test_injured_counts_as_medical(self):
        _, reasons = score_case(make(vulnerable=["injured"]), NOW)
        self.assertIn("medical need +15", reasons)

    def test_repeat_messages_bonus(self):
        _, reasons = score_case(make(mids=("a", "b", "c")), NOW)
        self.assertIn("3 messages +5", reasons)

    def test_bad_time_does_not_crash(self):
        self.assertEqual(score_case(make(t="not a time"), NOW)[0], 0)

    def test_rank_high_first_then_older(self):
        a = apply_score(make("a", t="2026-10-08T13:00:00", trapped=True), NOW)
        b = apply_score(make("b", t="2026-10-08T12:59:00", trapped=True), NOW)
        c = apply_score(make("c", water_level="roof", trapped=True), NOW)
        self.assertEqual([x.case_id for x in rank([a, b, c])], ["c", "b", "a"])

    def test_reasons_line(self):
        c = apply_score(make(trapped=True), NOW)
        self.assertEqual(reasons_line(c), "trapped +25 = 25")


if __name__ == "__main__":
    unittest.main(verbosity=2)
