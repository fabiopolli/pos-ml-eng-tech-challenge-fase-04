import pytest

from credit_monitoring.monitoring.report_context import build_report_context


@pytest.fixture
def report_inputs():
    features = ["LIMIT_BAL", "PAY_AMT1"]
    confusion = {"tn": 10, "fp": 2, "fn": 3, "tp": 4}
    metric = {
        "roc_auc": 0.77,
        "average_precision": 0.55,
        "precision": 0.66,
        "recall": 0.57,
        "f1": 0.61,
        "accuracy": 0.78,
        "brier": 0.18,
        "confusion_matrix": confusion,
    }
    model_metadata = {
        "selected_model": "random_forest",
        "model_sha256": "model-hash",
        "train_sha256": "train-hash",
        "threshold": 0.5,
        "random_seed": 42,
        "features": features,
        "hyperparameters": {
            "n_estimators": 300,
            "max_depth": 8,
            "min_samples_leaf": 20,
            "class_weight": "balanced_subsample",
        },
        "candidates": {
            "logistic_regression": {"hyperparameters": {"C": 1.0, "class_weight": "balanced"}},
            "random_forest_finalist": {
                "hyperparameters": {
                    "n_estimators": 600,
                    "max_depth": 12,
                    "max_features": 0.5,
                    "min_samples_leaf": 40,
                }
            },
        },
        "optimization": {
            "experiment_id": "campaign-1",
            "decision": {"action": "keep_current"},
            "candidates": {
                "random_forest_finalist": {
                    "algorithm": "random_forest",
                    "cv_mean_roc_auc": 0.7844,
                    "control_mean_roc_auc": 0.7809,
                    "validation_roc_auc": 0.7752,
                },
                "logistic_regression_finalist": {
                    "algorithm": "logistic_regression",
                    "cv_mean_roc_auc": 0.7255,
                    "control_mean_roc_auc": 0.7254,
                    "validation_roc_auc": 0.7145,
                },
            },
            "ablation": {"random_forest": {"gain": 0.0013, "min_gain_required": 0.005}},
        },
    }
    training_metrics = {
        "selected_model": "random_forest",
        "threshold": 0.5,
        "validation": {
            "random_forest": {**metric, "roc_auc": 0.7741},
            "logistic_regression": {**metric, "roc_auc": 0.7145},
            "random_forest_finalist": {**metric, "roc_auc": 0.7752},
            "logistic_regression_finalist": {**metric, "roc_auc": 0.7145},
        },
    }
    test_metrics = {
        "selected_model": "random_forest",
        "model_sha256": "model-hash",
        "threshold": 0.5,
        "test": metric,
        "test_exposure": {"declared": True},
    }
    preparation = {
        "cleaning": {"output_rows": 10, "removed_rows": 0},
        "raw_sha256": "raw-hash",
        "reference": {"train_sha256": "train-hash"},
        "splits": {
            "train": {"rows": 7, "target_rate": 0.2},
            "validation": {"rows": 2, "target_rate": 0.5},
            "test": {"rows": 1, "target_rate": 0.0},
        },
        "id_audit": {
            "coverage_complete": True,
            "ids_unique_within_split": {"train": True, "validation": True, "test": True},
            "id_intersections": {},
        },
    }
    optimization_manifest = {
        "experiment_id": "campaign-1",
        "inputs": {"train_sha256": "train-hash"},
        "folds": {"n_splits": 5, "random_state": 42},
        "trial_lists": {"random_forest": [1, 2], "logistic_regression": [1, 2, 3]},
    }
    optimization_comparison = {
        "decision": {"selected": "random_forest", "action": "keep_current"},
        "criteria_config": {
            "min_gain_validation": 0.01,
            "min_gain_cv_mean": 0.005,
        },
        "models": {"random_forest_finalist": {"contrast": {"ci_low": -0.002, "ci_high": 0.005}}},
    }
    dataset_summary = {
        "rows": 10,
        "columns": 25,
        "raw_sha256": "raw-hash",
        "target_counts": {"0": 8, "1": 2},
        "target_rate": 0.2,
    }
    prediction_summary = {
        "predictions": {
            "original": {
                "summary": {
                    "rows": 5,
                    "mean": 0.423,
                    "predicted_positives": 3,
                }
            },
            "modified": {
                "summary": {
                    "rows": 5,
                    "mean": 0.419,
                    "predicted_positives": 2,
                }
            },
        }
    }
    config = {
        "dataset": {
            "acquisition": {
                "source_url": "https://example.test/dataset",
                "doi": "10.0000/example",
                "license": "CC BY 4.0",
                "citation": "Example dataset citation",
            },
            "target_column_raw": "default payment next month",
            "id_column": "ID",
            "financial_features": features,
            "governance_features": ["AGE", "SEX"],
        }
    }
    comparisons = [
        {
            "reference_rows": 7,
            "current_rows": 5,
            "drifted_feature_count": 0,
            "drifted_features": [],
            "features": [
                {"feature": "LIMIT_BAL", "score": 0.01, "threshold": 0.2, "drift": False},
                {"feature": "PAY_AMT1", "score": 0.01, "threshold": 0.2, "drift": False},
            ],
        },
        {
            "current_rows": 5,
            "drifted_feature_count": 1,
            "drifted_features": ["LIMIT_BAL"],
            "features": [
                {"feature": "LIMIT_BAL", "score": 0.75, "threshold": 0.2, "drift": True},
                {"feature": "PAY_AMT1", "score": 0.01, "threshold": 0.2, "drift": False},
            ],
        },
    ]
    return {
        "dataset_summary": dataset_summary,
        "preparation": preparation,
        "training_metrics": training_metrics,
        "test_metrics": test_metrics,
        "model_metadata": model_metadata,
        "optimization_manifest": optimization_manifest,
        "optimization_comparison": optimization_comparison,
        "prediction_summary": prediction_summary,
        "config": config,
        "comparisons": comparisons,
    }


def test_report_context_connects_dataset_selection_and_drift_outputs(report_inputs):
    context = build_report_context(**report_inputs)

    assert "UCI Machine Learning Repository" in context["dataset_section"]
    assert "não demonstra ausência de viés" in context["dataset_section"]
    assert "7" in context["dataset_section"]
    assert "Random Forest" in context["training_section"]
    assert "0,7844" in context["training_section"]
    assert "0,7752" in context["training_section"]
    assert "600" in context["training_section"]
    assert "IC pareado de 95%" in context["training_section"]
    assert "inclui zero" in context["training_section"]
    assert "42,30%" in context["effect_section"]
    assert "41,90%" in context["effect_section"]
    assert "caiu em 1" in context["effect_section"]
    assert "não se calcula desempenho pós-drift" in context["effect_section"]


def test_report_context_rejects_a_model_hash_mismatch(report_inputs):
    report_inputs["test_metrics"]["model_sha256"] = "different-model"

    with pytest.raises(ValueError, match="Test metrics do not belong"):
        build_report_context(**report_inputs)
