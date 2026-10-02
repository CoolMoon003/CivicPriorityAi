import unittest
from types import SimpleNamespace

from backend.ai.detection_policy import (
    CONFIRMED,
    NO_RELIABLE_DETECTION,
    POSSIBLE,
    DetectionPolicy,
)
from backend.ai.road_damage_detector import (
    Detection,
    RoadDamageDetector,
    select_primary_detection,
)
from backend.app.scoring.priority_engine import PriorityEngine
from backend.app.services.damage_presentation import complaint_damage_fields


class DetectionConfidencePolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = DetectionPolicy(confirmed_threshold=0.25, possible_threshold=0.10)

    def test_confirmed_pothole_at_cutoff(self):
        self.assertEqual(self.policy.state_for(0.25), CONFIRMED)

    def test_possible_pothole_and_heavy_image_score(self):
        self.assertEqual(self.policy.state_for(0.2022), POSSIBLE)

    def test_weak_candidate_is_not_reliable(self):
        self.assertEqual(self.policy.state_for(0.0999), NO_RELIABLE_DETECTION)

    def test_no_detection_is_no_reliable(self):
        self.assertEqual(self.policy.state_for(None), NO_RELIABLE_DETECTION)

    def test_runtime_class_mapping_is_exact_and_ordered(self):
        RoadDamageDetector.validate_class_mapping({
            0: "Longitudinal Crack (D00)",
            1: "Transverse Crack (D10)",
            2: "Alligator Crack (D20)",
            3: "Pothole (D40)",
        })
        with self.assertRaises(ValueError):
            RoadDamageDetector.validate_class_mapping({
                0: "Pothole (D40)",
                1: "Transverse Crack (D10)",
                2: "Alligator Crack (D20)",
                3: "Longitudinal Crack (D00)",
            })

    def test_primary_selection_keeps_severity_order_transparent(self):
        possible_pothole = Detection(3, "Pothole (D40)", "pothole", .2022,
                                     1, 2, 3, 4, POSSIBLE, "high")
        confirmed_longitudinal = Detection(0, "Longitudinal Crack (D00)",
                                           "longitudinal_crack", .81,
                                           0, 0, 1, 1, CONFIRMED, "medium")
        self.assertIs(select_primary_detection([confirmed_longitudinal, possible_pothole]),
                      possible_pothole)

    def test_possible_damage_has_discounted_but_nonzero_priority_component(self):
        context = {"highway": "unclassified", "near_hospital": 1}
        possible = PriorityEngine.calculate("pothole", "high", 0.2022, context,
                                            detection_state=POSSIBLE)
        none = PriorityEngine.calculate("unknown", "unknown", 0.0, context,
                                        detection_state=NO_RELIABLE_DETECTION)
        self.assertEqual(possible.components["damage"]["value"], 20.22)
        self.assertEqual(possible.components["damage"]["undiscounted_value"], 100.0)
        self.assertNotEqual(possible.score, none.score)
        self.assertTrue(any("discounted" in message for message in possible.explanations))

    def test_unknown_legacy_severity_and_confidence_do_not_score(self):
        score = PriorityEngine.calculate("unknown", "medium", .8, {"highway": "primary"})
        self.assertIsNone(score.components["damage"]["value"])
        self.assertIsNone(score.components["confidence"]["value"])
        legacy = complaint_damage_fields(SimpleNamespace(
            damage_type="unknown", damage_severity="medium", damage_confidence=.8
        ))
        self.assertEqual(legacy["type"], "unknown")
        self.assertEqual(legacy["severity"], "unknown")
        self.assertEqual(legacy["confidence"], 0.0)
        self.assertEqual(legacy["detection_state"], NO_RELIABLE_DETECTION)

    def test_stale_known_class_below_possible_threshold_is_normalized(self):
        legacy = complaint_damage_fields(SimpleNamespace(
            damage_type="pothole", damage_severity="high", damage_confidence=.05
        ))
        self.assertEqual(legacy["type"], "unknown")
        self.assertEqual(legacy["severity"], "unknown")
        self.assertEqual(legacy["confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()
