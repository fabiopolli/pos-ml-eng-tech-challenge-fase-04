"""Structural audit of the raw credit card default dataset.

This module is deliberately restricted to **structural** facts about the raw file:
shape, missing values, duplicates, code domains and marginal feature distributions.
Anything that relates a feature to the target is *supervised exploration* and lives in
:mod:`credit_monitoring.explore`, which runs on the training split only (see delivery
1.2 of the phase plan: the historical EDA computed correlations on the full raw file,
which includes the future test partition).
"""

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from credit_monitoring.config import load_config  # noqa: E402
from credit_monitoring.data.loading import default_raw_path, file_sha256, load_raw  # noqa: E402
from credit_monitoring.paths import EDA_REPORT_DIR, FIGURES_DIR  # noqa: E402

SUMMARY_FILE = "eda_summary.json"
DEFAULT_FIGURES_DIR = FIGURES_DIR / "eda"
DEFAULT_SUMMARY_PATH = EDA_REPORT_DIR / SUMMARY_FILE

# Codes documented by the dataset authors; anything else is reported, never recoded.
DOCUMENTED_CODES = {
    "SEX": {1, 2},
    "EDUCATION": {1, 2, 3, 4},
    "MARRIAGE": {1, 2, 3},
}
PAY_COLUMNS = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]
BILL_COLUMNS = [f"BILL_AMT{i}" for i in range(1, 7)]
PAY_AMT_COLUMNS = [f"PAY_AMT{i}" for i in range(1, 7)]
AMOUNT_COLUMNS = ["LIMIT_BAL", *BILL_COLUMNS, *PAY_AMT_COLUMNS]
DPI = 150


def _target(config: dict[str, Any]) -> str:
    return config["dataset"]["canonical_target"]


def _iqr_outliers(series: pd.Series) -> int:
    q1, q3 = series.quantile([0.25, 0.75])
    spread = q3 - q1
    return int(((series < q1 - 1.5 * spread) | (series > q3 + 1.5 * spread)).sum())


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def build_summary(
    raw: pd.DataFrame, config: dict[str, Any], *, raw_sha256: str, raw_file: str
) -> dict[str, Any]:
    """Structural summary of the raw file; no feature-to-target relationship is computed."""
    target = _target(config)
    id_column = config["dataset"]["id_column"]

    undocumented = {
        column: raw.loc[~raw[column].isin(codes), column].value_counts().sort_index().to_dict()
        for column, codes in DOCUMENTED_CODES.items()
    }
    pay_values = pd.concat([raw[column] for column in PAY_COLUMNS])
    undocumented["PAY"] = pay_values[pay_values.isin([-2, 0])].value_counts().sort_index().to_dict()

    summary = {
        "raw_file": raw_file,
        "raw_sha256": raw_sha256,
        "scope": "structural_audit_only",
        "supervised_analysis": False,
        "rows": len(raw),
        "columns": raw.shape[1],
        "null_values": int(raw.isna().sum().sum()),
        "duplicated_rows": int(raw.duplicated().sum()),
        "duplicated_ids": int(raw[id_column].duplicated().sum()),
        "non_numeric_columns": [
            column for column in raw.columns if not pd.api.types.is_numeric_dtype(raw[column])
        ],
        # Marginal class balance over the whole raw file. It is inherent to the
        # stratified 70/15/15 protocol and carries no feature-to-target relationship.
        "target_counts": raw[target].value_counts().sort_index().to_dict(),
        "target_rate": float(raw[target].mean()),
        "age_min": int(raw["AGE"].min()),
        "age_max": int(raw["AGE"].max()),
        "limit_bal_min": int(raw["LIMIT_BAL"].min()),
        "limit_bal_max": int(raw["LIMIT_BAL"].max()),
        "limit_bal_non_positive": int((raw["LIMIT_BAL"] <= 0).sum()),
        "negative_bill_amt_values": int((raw[BILL_COLUMNS] < 0).sum().sum()),
        "negative_pay_amt_values": int((raw[PAY_AMT_COLUMNS] < 0).sum().sum()),
        "undocumented_codes": undocumented,
        "iqr_outliers": {column: _iqr_outliers(raw[column]) for column in AMOUNT_COLUMNS},
    }
    return _jsonable(summary)


def _save(fig: plt.Figure, figures_dir: Path, name: str) -> Path:
    figures_dir.mkdir(parents=True, exist_ok=True)
    path = figures_dir / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_target_distribution(raw: pd.DataFrame, config: dict[str, Any], figures_dir: Path) -> Path:
    """Marginal class balance only; no feature is involved."""
    target = _target(config)
    counts = raw[target].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(5, 4))
    sns.barplot(x=counts.index.astype(str), y=counts.values, ax=ax, color="#4c72b0")
    for position, value in enumerate(counts.values):
        ax.text(position, value, f"{value} ({value / counts.sum():.1%})", ha="center", va="bottom")
    ax.set(title="Distribuição do alvo (bruto, marginal)", xlabel=target, ylabel="Clientes")
    return _save(fig, figures_dir, "01_target_distribution.png")


def plot_age_distribution(raw: pd.DataFrame, config: dict[str, Any], figures_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.histplot(raw["AGE"], bins=30, ax=ax, color="#4c72b0")
    ax.set(title="Distribuição de AGE (bruto)", xlabel="AGE (anos)", ylabel="Clientes")
    return _save(fig, figures_dir, "02_age_distribution.png")


def plot_limit_bal_distribution(
    raw: pd.DataFrame, config: dict[str, Any], figures_dir: Path
) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.histplot(raw["LIMIT_BAL"], bins=40, log_scale=True, ax=ax, color="#4c72b0")
    ax.set(title="LIMIT_BAL (escala log, bruto)", xlabel="LIMIT_BAL (NT$)", ylabel="Clientes")
    return _save(fig, figures_dir, "03_limit_bal_distribution.png")


def _plot_amounts(
    raw: pd.DataFrame, columns: list[str], title: str, figures_dir: Path, name: str
) -> Path:
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.boxplot(data=raw[columns], ax=ax, color="#8172b2", fliersize=1)
    ax.set_yscale("symlog", linthresh=1000)
    ax.set(title=title, ylabel="NT$ (symlog)")
    return _save(fig, figures_dir, name)


def plot_bill_amounts(raw: pd.DataFrame, config: dict[str, Any], figures_dir: Path) -> Path:
    return _plot_amounts(
        raw,
        BILL_COLUMNS,
        "BILL_AMT1..6 (inclui valores negativos)",
        figures_dir,
        "04_bill_amt_distribution.png",
    )


def plot_pay_amounts(raw: pd.DataFrame, config: dict[str, Any], figures_dir: Path) -> Path:
    return _plot_amounts(
        raw, PAY_AMT_COLUMNS, "PAY_AMT1..6", figures_dir, "05_pay_amt_distribution.png"
    )


def plot_payment_status_counts(
    raw: pd.DataFrame, config: dict[str, Any], figures_dir: Path
) -> Path:
    counts = pd.DataFrame({column: raw[column].value_counts() for column in PAY_COLUMNS})
    counts = counts.sort_index().fillna(0).astype(int)
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.heatmap(counts, annot=True, fmt="d", cmap="Blues", ax=ax)
    ax.set(title="Status de pagamento (contagem, bruto)", xlabel="Variável", ylabel="Status")
    return _save(fig, figures_dir, "06_payment_status_counts.png")


PLOTS: list[Callable[[pd.DataFrame, dict[str, Any], Path], Path]] = [
    plot_target_distribution,
    plot_age_distribution,
    plot_limit_bal_distribution,
    plot_bill_amounts,
    plot_pay_amounts,
    plot_payment_status_counts,
]


def run_eda(
    raw_csv: str | Path,
    config: dict[str, Any],
    *,
    figures_dir: str | Path = DEFAULT_FIGURES_DIR,
    summary_path: str | Path = DEFAULT_SUMMARY_PATH,
) -> dict[str, Any]:
    raw_csv = Path(raw_csv)
    raw = load_raw(raw_csv, config)
    summary = build_summary(raw, config, raw_sha256=file_sha256(raw_csv), raw_file=raw_csv.name)
    figures_path = Path(figures_dir)
    for plot in PLOTS:
        plot(raw, config, figures_path)
    summary_path = Path(summary_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera a auditoria estrutural do bruto.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--raw-csv", default=None)
    parser.add_argument("--figures-dir", default=str(DEFAULT_FIGURES_DIR))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    args = parser.parse_args(argv)

    config = load_config(args.config)
    raw_csv = args.raw_csv or default_raw_path(config)
    summary = run_eda(raw_csv, config, figures_dir=args.figures_dir, summary_path=args.summary_path)
    print(
        f"EDA concluida: {summary['rows']} linhas, "
        f"taxa de default marginal {summary['target_rate']:.2%} (analise supervisionada no treino)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
