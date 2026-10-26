"""Tests of the model laboratory application (plan 1.6, package 1.6-O6).

The application is exercised with ``streamlit.testing.v1.AppTest``. The tests
check the states the plan requires: empty catalogue, missing artifact, valid
comparison, contract failure, and the absence of any ``fit`` or evaluation call.

The tests are skipped when the ``model_lab`` extra is not installed, so the
standard environment keeps running the rest of the suite.
"""

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

APP_PATH = str(Path(__file__).resolve().parents[1] / "dashboard" / "app_dev.py")


def _app() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=120)


def _module():
    """Import the application module outside of a Streamlit run."""
    spec = importlib.util.spec_from_file_location("credit_monitoring_lab_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_application_starts_and_exposes_the_four_tabs():
    at = _app().run()

    assert not at.exception
    labels = [tab.label for tab in at.tabs]
    assert labels[:3] == [
        "Artefatos e prontidao",
        "Comparacao dos modelos",
        "Predicao",
    ]
    assert "Cenarios de contrato" in labels
    assert "Registro individual" in labels
    assert "Lote CSV" in labels


def test_the_application_never_fits_or_evaluates_a_model(monkeypatch):
    """Opening the laboratory must not train, promote or evaluate anything."""
    from sklearn.pipeline import Pipeline

    import credit_monitoring.models.evaluate as evaluate_module

    calls: list[str] = []
    original_fit = Pipeline.fit
    original_evaluation = evaluate_module.run_evaluation

    def counting_fit(self, *args, **kwargs):
        calls.append("fit")
        return original_fit(self, *args, **kwargs)

    def counting_evaluation(*args, **kwargs):
        calls.append("evaluate")
        return original_evaluation(*args, **kwargs)

    monkeypatch.setattr(Pipeline, "fit", counting_fit)
    monkeypatch.setattr(evaluate_module, "run_evaluation", counting_evaluation)

    at = _app().run()

    assert not at.exception
    assert calls == []


def test_the_application_runs_without_any_artifact(tmp_path, monkeypatch):
    """The empty state is explicit: the application still starts."""
    import credit_monitoring.paths as paths

    monkeypatch.setattr(paths, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(paths, "REPORTS_DIR", tmp_path / "reports")

    at = _app().run()

    assert not at.exception


def test_the_presets_cover_the_contract_rules():
    """One valid preset and four violations, all synthetic."""
    from credit_monitoring.config import load_config

    app_dev = _module()

    presets = app_dev.preset_frames(load_config())

    assert set(presets) == {
        "valid",
        "duplicate_id",
        "non_positive_limit",
        "age_out_of_range",
        "null_feature",
    }
    assert all(
        isinstance(title, str) and expectation for _f, title, expectation in presets.values()
    )


def test_an_invalid_preset_triggers_zero_calls_to_the_models():
    """The diagnostic is produced and no selected model is called."""
    from credit_monitoring.config import load_config
    from credit_monitoring.contracts import ContractViolation

    app_dev = _module()
    from credit_monitoring.models.inference import compare_models

    config = load_config()
    presets = app_dev.preset_frames(config)
    calls: list[str] = []

    class Spy:
        def predict_proba(self, features):
            calls.append("predict_proba")
            import numpy as np

            return np.tile(np.array([0.5, 0.5]), (len(features), 1))

    for key, (frame, _title, _expectation) in presets.items():
        calls.clear()
        if key == "valid":
            compare_models({"spy": Spy()}, frame, config)
            assert calls, "the valid preset must reach the model"
            continue
        with pytest.raises(ContractViolation):
            compare_models({"spy": Spy()}, frame, config)
        assert calls == [], f"the invalid preset '{key}' reached the model"


def test_the_curves_are_plotted_as_two_series_and_not_as_a_two_dimensional_dataset():
    """Regression: a tuple of sequences must not become one line per row.

    ``Axes.plot`` reads a tuple of sequences as a two-dimensional dataset and
    draws one line per observation. With the validation round that produced
    thousands of artists per axis, a render that took minutes and an image
    large enough to be refused as a decompression bomb.
    """
    import pandas as pd

    app_dev = _module()

    rows = 500
    predictions = pd.DataFrame(
        {
            "target": [index % 2 for index in range(rows)],
            "random_forest": [(index % 7) / 7 for index in range(rows)],
            "random_forest_finalist": [(index % 11) / 11 for index in range(rows)],
        }
    )
    models = {"random_forest": {}, "random_forest_finalist": {}}

    figure = app_dev.curves_figure(predictions, models, "target")

    roc_axis, precision_axis = figure.axes
    assert len(roc_axis.lines) == 3, "one line per model plus the diagonal reference"
    assert len(precision_axis.lines) == 2, "one line per model"
    total_points = sum(len(line.get_xdata()) for axis in figure.axes for line in axis.lines)
    assert total_points <= 4 * rows, "each curve is a single series, not one line per row"
    bbox = figure.get_tightbbox()
    assert bbox.height < 1_000 and bbox.width < 2_000, "the figure must stay within a sane size"


def test_the_distribution_figure_is_a_figure_with_one_axis():
    import pandas as pd

    app_dev = _module()

    distribution = pd.DataFrame(
        {
            "random_forest": [0.1, 0.4, 0.7, 0.9],
            "random_forest_finalist": [0.2, 0.3, 0.6, 0.8],
        }
    )

    figure = app_dev.distribution_figure(distribution)

    assert len(figure.axes) == 1
    assert figure.axes[0].get_xlabel() == "Probabilidade de inadimplencia"


def test_the_result_is_invalidated_when_the_selection_changes():
    """A stored result is only shown while it still matches the selection."""
    import pandas as pd

    app_dev = _module()

    frame = pd.DataFrame({"LIMIT_BAL": [1.0]})
    first = app_dev._signature(["random_forest"], frame)
    second = app_dev._signature(["random_forest", "random_forest_finalist"], frame)

    assert first != second
