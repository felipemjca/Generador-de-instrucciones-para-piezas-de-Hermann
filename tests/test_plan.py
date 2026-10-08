import unittest

from instruction_app.generation_plan import build_generation_plan
from instruction_app.validation import normalize_payload
from tests.sample_data import sample_payload


class GenerationPlanTests(unittest.TestCase):
    def test_single_sequence_creates_only_one_visual_step_and_one_page(self):
        plan = build_generation_plan(normalize_payload(sample_payload(1)))
        self.assertEqual(plan["page_count"], 1)
        self.assertEqual(len(plan["pages"]), 1)
        self.assertEqual(len(plan["pages"][0]["sequences"]), 1)
        self.assertEqual(len(plan["visual_rows"]), 1)
        self.assertEqual(len(plan["visual_rows"][0]), 1)

    def test_five_sequences_per_numbered_sheet(self):
        plan = build_generation_plan(normalize_payload(sample_payload(11)))
        self.assertEqual(plan["page_count"], 3)
        self.assertEqual([len(page["sequences"]) for page in plan["pages"]], [5, 5, 1])

    def test_visual_contains_every_step_in_rows_of_three(self):
        plan = build_generation_plan(normalize_payload(sample_payload(7)))
        self.assertEqual([len(row) for row in plan["visual_rows"]], [3, 3, 1])
        self.assertEqual(sum(map(len, plan["visual_rows"])), 7)

    def test_automatic_document_uses_normalized_station(self):
        plan = build_generation_plan(normalize_payload(sample_payload(1)))
        self.assertEqual(plan["documents"][0], "SETEO ESTÁNDAR P08")


if __name__ == "__main__":
    unittest.main()
