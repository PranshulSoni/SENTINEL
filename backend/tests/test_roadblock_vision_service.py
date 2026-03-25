import unittest

from services.roadblock_vision_service import RoadblockVisionService, score_to_severity


class RoadblockVisionServiceTests(unittest.TestCase):
    def setUp(self):
        self.svc = RoadblockVisionService(provider="hf", api_token="token")

    def test_score_to_severity_bands(self):
        self.assertEqual(score_to_severity(0), "minor")
        self.assertEqual(score_to_severity(24), "minor")
        self.assertEqual(score_to_severity(25), "moderate")
        self.assertEqual(score_to_severity(49), "moderate")
        self.assertEqual(score_to_severity(50), "major")
        self.assertEqual(score_to_severity(74), "major")
        self.assertEqual(score_to_severity(75), "critical")
        self.assertEqual(score_to_severity(100), "critical")

    def test_parse_strict_json_true(self):
        out = self.svc._parse_response(
            {
                "roadblock_detected": True,
                "obstruction_score": 83,
                "explanation": "Collision blocking two lanes",
            }
        )
        self.assertTrue(out.roadblock_detected)
        self.assertEqual(out.obstruction_score, 83)
        self.assertEqual(out.confidence_score, 83)
        self.assertEqual(out.severity, "critical")
        self.assertTrue(out.parse_valid)

    def test_parse_strict_json_false(self):
        out = self.svc._parse_response(
            {
                "roadblock_detected": False,
                "obstruction_score": 10,
                "explanation": "No blockage detected",
            }
        )
        self.assertFalse(out.roadblock_detected)
        self.assertTrue(out.parse_valid)
        self.assertEqual(out.confidence_score, 15)

    def test_rejects_non_json_text(self):
        out = self.svc._parse_response("I think there might be an accident")
        self.assertFalse(out.roadblock_detected)
        self.assertFalse(out.parse_valid)
        self.assertEqual(out.confidence_score, 0)

    def test_rejects_json_without_boolean_flag(self):
        out = self.svc._parse_response(
            {
                "roadblock_detected": "true",
                "obstruction_score": 90,
                "explanation": "String bool should be rejected for strict parsing",
            }
        )
        self.assertFalse(out.roadblock_detected)
        self.assertFalse(out.parse_valid)

    def test_legacy_hf_url_is_auto_upgraded_to_router(self):
        svc = RoadblockVisionService(
            provider="hf",
            api_token="token",
            model_url="https://api-inference.huggingface.co/models/llava-hf/llava-1.5-7b-hf",
        )
        self.assertTrue(svc.model_url.startswith("https://router.huggingface.co/hf-inference/models/"))
        self.assertIn("llava-hf/llava-1.5-7b-hf", svc.model_url)

    def test_ollama_response_key_is_parsed(self):
        svc = RoadblockVisionService(provider="ollama", ollama_model="llava")
        out = svc._parse_response(
            {
                "model": "llava",
                "response": '{"roadblock_detected": true, "obstruction_score": 68, "explanation": "Accident blocking lane"}',
            }
        )
        self.assertTrue(out.roadblock_detected)
        self.assertEqual(out.obstruction_score, 68)
        self.assertEqual(out.severity, "major")

    def test_ollama_data_url_base64_extraction(self):
        svc = RoadblockVisionService(provider="ollama", ollama_model="llava")
        b64 = svc._normalize_image_input_for_ollama("data:image/jpeg;base64,AAAA")
        self.assertEqual(b64, "AAAA")


if __name__ == "__main__":
    unittest.main()
