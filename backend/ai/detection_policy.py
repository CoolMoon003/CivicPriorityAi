"""Central confidence states shared by the detector, scorer, and API."""
from __future__ import annotations

from dataclasses import dataclass
import os


CONFIRMED = "confirmed"
POSSIBLE = "possible"
NO_RELIABLE_DETECTION = "no_reliable_detection"


@dataclass(frozen=True)
class DetectionPolicy:
    confirmed_threshold: float = 0.25
    possible_threshold: float = 0.10
    inference_size: int = 640
    fallback_inference_size: int = 1280

    @classmethod
    def from_environment(cls) -> "DetectionPolicy":
        # Keep the existing setting as a backwards-compatible confirmed cutoff.
        confirmed = os.getenv(
            "CIVIC_DAMAGE_CONFIRMED_THRESHOLD",
            os.getenv("CIVIC_ROAD_DAMAGE_CONFIDENCE", "0.25"),
        )
        possible = os.getenv("CIVIC_DAMAGE_POSSIBLE_THRESHOLD", "0.10")
        image_size = os.getenv("CIVIC_DAMAGE_INFERENCE_SIZE", "640")
        fallback_size = os.getenv("CIVIC_DAMAGE_FALLBACK_INFERENCE_SIZE", "1280")
        try:
            policy = cls(float(confirmed), float(possible), int(image_size), int(fallback_size))
        except ValueError as exc:
            raise ValueError(
                "Detection policy requires numeric thresholds and an integer inference size"
            ) from exc
        policy.validate()
        return policy

    def validate(self) -> None:
        if not 0 <= self.possible_threshold <= self.confirmed_threshold <= 1:
            raise ValueError(
                "Detection thresholds must satisfy 0 <= possible <= confirmed <= 1"
            )
        if self.inference_size < 32:
            raise ValueError("CIVIC_DAMAGE_INFERENCE_SIZE must be at least 32")
        if self.fallback_inference_size != 0 and self.fallback_inference_size < 32:
            raise ValueError("CIVIC_DAMAGE_FALLBACK_INFERENCE_SIZE must be 0 or at least 32")

    def state_for(self, confidence: float | None) -> str:
        value = float(confidence or 0.0)
        if value >= self.confirmed_threshold:
            return CONFIRMED
        if value >= self.possible_threshold:
            return POSSIBLE
        return NO_RELIABLE_DETECTION


DEFAULT_POLICY = DetectionPolicy.from_environment()
