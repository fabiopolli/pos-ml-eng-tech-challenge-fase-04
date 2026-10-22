from credit_monitoring import __version__
from credit_monitoring.paths import (
    CONFIG_DIR,
    DATA_DIR,
    MODELS_DIR,
    PRODUCTION_DATA_DIR,
    REFERENCE_DATA_DIR,
    REPORTS_DIR,
)


def test_package_version() -> None:
    assert __version__ == "0.1.0"


def test_expected_project_directories_exist() -> None:
    expected = [
        CONFIG_DIR,
        DATA_DIR,
        REFERENCE_DATA_DIR,
        PRODUCTION_DATA_DIR,
        MODELS_DIR,
        REPORTS_DIR,
    ]
    assert all(path.is_dir() for path in expected)
