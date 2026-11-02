"""Supervised exploration of the training split.

Feature-to-target relationships are only computed here, and only on the training
partition. The historical EDA computed them on the full raw file (30.000 rows), which
included the rows later assigned to the test partition; that exposure is declared in
`docs/evidence/fase-1.md` and the historical artifact is kept as a contaminated record
under `reports/eda/history/`.
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
from credit_monitoring.paths import FIGURES_DIR, PROCESSED_DATA_DIR, REPORTS_DIR  # noqa: E402

SUMMARY_FILE = "train_exploration.json"
DEFAULT_FIGURES_DIR = FIGURES_DIR / "explore"
DEFAULT_SUMMARY_PATH = REPORTS_DIR / "explore" / SUMMARY_FILE
DPI = 150


def _target(config: dict[str, Any]) -> str:
    return config["dataset"]["canonical_target"]


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


def build_summary(train: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """Feature-to-target relationships measured on the training split only."""
    target = _target(config)
    features = config["dataset"]["financial_features"]

    correlations = train[[*features, target]].corr()[target].drop(target)
    top = correlations.reindex(correlations.abs().sort_values(ascending=False).index).head(10)

    group_rates = {}
    for column in ["SEX", "EDUCATION", "MARRIAGE"]:
        grouped = train.groupby(column)[target].agg(["mean", "size"])
        group_rates[column] = {
            str(level): {"default_rate": round(float(row["mean"]), 6), "rows": int(row["size"])}
            for level, row in grouped.iterrows()
        }

    bands = pd.cut(train["AGE"], bins=[17, 25, 30, 35, 40, 50, 60, 100])
    age_rate = train.groupby(bands, observed=True)[target].agg(["mean", "size"])

    return _jsonable(
        {
            "scope": "training_split_only",
            "split": "train",
            "rows": len(train),
            "target_rate": float(train[target].mean()),
            "top_target_correlations": top.round(4).to_dict(),
            "default_rate_by_group": group_rates,
            "default_rate_by_age_band": {
                str(band): {"default_rate": round(float(row["mean"]), 6), "rows": int(row["size"])}
                for band, row in age_rate.iterrows()
            },
        }
    )


def _save(fig: plt.Figure, figures_dir: Path, name: str) -> Path:
    figures_dir.mkdir(parents=True, exist_ok=True)
    path = figures_dir / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_target_correlation(train: pd.DataFrame, config: dict[str, Any], figures_dir: Path) -> Path:
    target = _target(config)
    features = config["dataset"]["financial_features"]
    correlation = train[[*features, target]].corr()[target].drop(target).sort_values()
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.barh(correlation.index, correlation.values, color="#4c72b0")
    ax.set(title="Correlacao das features com o alvo (treino)", xlabel="Pearson")
    return _save(fig, figures_dir, "01_target_correlation.png")


def plot_correlation_heatmap(
    train: pd.DataFrame, config: dict[str, Any], figures_dir: Path
) -> Path:
    columns = [*config["dataset"]["financial_features"], _target(config)]
    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(train[columns].corr(), cmap="coolwarm", center=0, ax=ax, square=True)
    ax.set_title("Correlacao (features financeiras + alvo) - treino")
    return _save(fig, figures_dir, "02_correlation_heatmap.png")


def plot_categorical_default_rate(
    train: pd.DataFrame, config: dict[str, Any], figures_dir: Path
) -> Path:
    target = _target(config)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    for ax, column in zip(axes, ["SEX", "EDUCATION", "MARRIAGE"], strict=True):
        grouped = train.groupby(column)[target].agg(["mean", "size"])
        sns.barplot(x=grouped.index.astype(str), y=grouped["mean"], ax=ax, color="#55a868")
        for position, (rate, size) in enumerate(zip(grouped["mean"], grouped["size"], strict=True)):
            ax.text(position, rate, f"n={size}", ha="center", va="bottom", fontsize=8)
        ax.axhline(train[target].mean(), color="red", linestyle="--", linewidth=1)
        ax.set(title=f"Taxa de default por {column}", xlabel=column, ylabel="Taxa de default")
    return _save(fig, figures_dir, "03_categorical_default_rate.png")


def plot_age_default_rate(train: pd.DataFrame, config: dict[str, Any], figures_dir: Path) -> Path:
    target = _target(config)
    bands = pd.cut(train["AGE"], bins=[17, 25, 30, 35, 40, 50, 60, 100])
    rate = train.groupby(bands, observed=True)[target].mean()
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(x=rate.index.astype(str), y=rate.values, ax=ax, color="#55a868")
    ax.set(
        title="Taxa de default por faixa etaria (treino)",
        xlabel="AGE",
        ylabel="Taxa de default",
    )
    ax.tick_params(axis="x", rotation=30)
    return _save(fig, figures_dir, "04_age_default_rate.png")


def plot_payment_status_default_rate(
    train: pd.DataFrame, config: dict[str, Any], figures_dir: Path
) -> Path:
    target = _target(config)
    rate = train.groupby("PAY_0")[target].mean()
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.barplot(x=rate.index.astype(str), y=rate.values, ax=ax, color="#c44e52")
    ax.set(title="Taxa de default por PAY_0 (treino)", xlabel="PAY_0", ylabel="Taxa de default")
    return _save(fig, figures_dir, "05_payment_status_default_rate.png")


def plot_limit_bal_by_target(
    train: pd.DataFrame, config: dict[str, Any], figures_dir: Path
) -> Path:
    target = _target(config)
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.boxplot(
        data=train,
        x=target,
        y="LIMIT_BAL",
        hue=target,
        legend=False,
        ax=ax,
    )
    ax.set_yscale("symlog", linthresh=1000)
    ax.set(title="LIMIT_BAL por alvo (treino)", xlabel=target, ylabel="LIMIT_BAL (NT$)")
    return _save(fig, figures_dir, "06_limit_bal_by_target.png")


PLOTS: list[Callable[[pd.DataFrame, dict[str, Any], Path], Path]] = [
    plot_target_correlation,
    plot_correlation_heatmap,
    plot_categorical_default_rate,
    plot_age_default_rate,
    plot_payment_status_default_rate,
    plot_limit_bal_by_target,
]


def run_exploration(
    train_csv: str | Path,
    config: dict[str, Any],
    *,
    figures_dir: str | Path = DEFAULT_FIGURES_DIR,
    summary_path: str | Path = DEFAULT_SUMMARY_PATH,
) -> dict[str, Any]:
    train_csv = Path(train_csv)
    train = pd.read_csv(train_csv)
    summary = build_summary(train, config)
    figures_path = Path(figures_dir)
    for plot in PLOTS:
        plot(train, config, figures_path)
    summary_path = Path(summary_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exploracao supervisionada restrita ao split de treino."
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--train-csv", default=str(PROCESSED_DATA_DIR / "train.csv"))
    parser.add_argument("--figures-dir", default=str(DEFAULT_FIGURES_DIR))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    args = parser.parse_args(argv)

    config = load_config(args.config)
    summary = run_exploration(
        args.train_csv,
        config,
        figures_dir=args.figures_dir,
        summary_path=args.summary_path,
    )
    print(
        f"Exploracao supervisionada concluida no treino: {summary['rows']} linhas, "
        f"taxa de default {summary['target_rate']:.2%}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
