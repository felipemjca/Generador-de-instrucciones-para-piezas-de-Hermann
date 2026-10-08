import unittest

from instruction_app.validation import normalize_payload, validate_payload
from tests.sample_data import sample_payload


class ValidationTests(unittest.TestCase):
    def test_normalizes_station_model_and_fixed_control_fields(self):
        raw = sample_payload()
        raw["sequences"][0]["safety_symbol"] = "on"
        raw["sequences"][0]["quality_symbol"] = "false"
        raw["sequences"][0]["triangle_s_number"] = " 4 "
        payload = normalize_payload(raw)
        self.assertEqual(payload["general"]["station"], "08")
        self.assertEqual(payload["general"]["model"], "ESTÁNDAR")
        self.assertEqual(payload["controls"][0]["measurement"], "Visual")
        self.assertEqual(payload["controls"][0]["sampling"], "100%")
        self.assertTrue(payload["sequences"][0]["safety_symbol"])
        self.assertFalse(payload["sequences"][0]["quality_symbol"])
        self.assertEqual(payload["sequences"][0]["triangle_s_number"], "4")
        self.assertEqual(validate_payload(payload), [])

    def test_rejects_a_non_numeric_triangle_s_marker(self):
        raw = sample_payload(1)
        raw["sequences"][0]["triangle_s_number"] = "4A"
        errors = validate_payload(normalize_payload(raw))
        self.assertTrue(any("marcador △S" in error for error in errors))

    def test_preserves_zero_as_a_valid_triangle_s_marker(self):
        raw = sample_payload(1)
        raw["sequences"][0]["triangle_s_number"] = 0
        payload = normalize_payload(raw)
        self.assertEqual(payload["sequences"][0]["triangle_s_number"], "0")
        self.assertEqual(validate_payload(payload), [])

    def test_discards_legacy_image_annotation_state(self):
        raw = sample_payload(1)
        raw["sequences"][0]["annotation_data"] = '{"version":1,"objects":[]}'
        payload = normalize_payload(raw)
        self.assertEqual(payload["sequences"][0]["annotation_data"], {})
        self.assertEqual(validate_payload(payload), [])

    def test_fills_empty_sequence_and_visual_summary_as_incomplete(self):
        raw = sample_payload(1)
        raw["sequences"][0]["sequence"] = ""
        raw["sequences"][0]["visual_summary"] = ""
        payload = normalize_payload(raw)
        self.assertEqual(payload["sequences"][0]["sequence"], "* Incompleto")
        self.assertEqual(payload["sequences"][0]["visual_summary"], "* Incompleto")
        self.assertEqual(validate_payload(payload), [])

    def test_key_point_and_reason_are_paired(self):
        raw = sample_payload(1)
        raw["sequences"][0]["key_point"] = "Posición exacta"
        errors = validate_payload(normalize_payload(raw))
        self.assertTrue(any("punto clave y razón" in error for error in errors))

    def test_controls_may_be_empty(self):
        raw = sample_payload(1)
        raw["controls"] = []
        self.assertEqual(validate_payload(normalize_payload(raw)), [])


if __name__ == "__main__":
    unittest.main()
