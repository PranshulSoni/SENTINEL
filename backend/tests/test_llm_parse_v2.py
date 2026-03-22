import unittest

from services.llm_service import LLMService


class LLMParseV2Tests(unittest.TestCase):
    def test_parses_all_five_sections(self):
        raw = """[SIGNAL_RETIMING]
Extend northbound green on W 34th St & 7th Ave from 45s to 90s.
[DIVERSIONS]
Diversion A: 10th Ave -> W 42nd St -> 9th Ave. Expected to absorb ~60%.
[ALERTS]
VMS: ACCIDENT W 34TH ST
RADIO: Expect delays in corridor.
SOCIAL: Traffic alert.
[NARRATIVE_UPDATE]
Incident remains active with heavy queues.
[CCTV_SUMMARY]
Camera confirms two stationary vehicles and road blockage.
"""
        parsed = LLMService.parse_structured_output_v2(raw)
        self.assertEqual(parsed.get("version"), "v2")
        self.assertEqual(len(parsed.get("sections_present", [])), 5)
        self.assertTrue(parsed["alerts"]["vms"])
        self.assertTrue(parsed["narrative_update"])
        self.assertTrue(parsed["cctv_summary"])

    def test_degrades_gracefully_without_sections(self):
        raw = "Traffic incident with delays. Extend green at W 34th St."
        parsed = LLMService.parse_structured_output_v2(raw)
        self.assertEqual(parsed.get("version"), "v2")
        self.assertTrue(parsed["narrative_update"])
        self.assertTrue(parsed["signal_retiming"]["intersections"])


if __name__ == "__main__":
    unittest.main()
