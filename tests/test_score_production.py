import numpy as np

from credit_monitoring.models.inference import InferenceResult
from credit_monitoring.models.score_production import (
    _persisted_probabilities,
    _stable_inference_summary,
)


def test_persisted_inference_summary_excludes_local_paths_and_runtime():
    result = InferenceResult(
        rows=2,
        probability=np.array([0.2, 0.8]),
        predicted=np.array([0, 1]),
        threshold=0.5,
        duration_s=0.012345,
        model_sha256="a" * 64,
    )
    repeated = InferenceResult(
        rows=2,
        probability=np.array([0.2 + 1e-16, 0.8 - 1e-16]),
        predicted=np.array([0, 1]),
        threshold=0.5,
        duration_s=9.876543,
        model_sha256="a" * 64,
    )

    rounded, classes = _persisted_probabilities(result, decimals=12)
    summary = _stable_inference_summary(result, rounded, classes)

    repeated_rounded, repeated_classes = _persisted_probabilities(repeated, decimals=12)
    np.testing.assert_array_equal(rounded, repeated_rounded)
    np.testing.assert_array_equal(classes, repeated_classes)
    assert summary == _stable_inference_summary(repeated, repeated_rounded, repeated_classes)
    assert "duration_s" not in summary
    assert "path" not in summary
