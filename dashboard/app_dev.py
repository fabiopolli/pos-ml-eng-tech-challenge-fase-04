"""Model laboratory of the credit scoring project (plan 1.6, package ``1.6-O6``).

A local Streamlit application to **inspect, compare and test** the published model,
the two serialized controls and the finalists of the optimization campaign.

What this application is:

- a read-only laboratory. It never trains, never promotes a model, never writes over a
  dataset, over the official metrics or over ``dvc.lock``;
- a comparison surface: the side-by-side table of the frozen validation round, the
  paired bootstrap intervals, the confusion matrices and the ROC/PR curves of exactly
  those models, with the origin of every number;
- a test surface: an editable financial form and a CSV batch, scored by the frozen
  pipelines through the shared inference service.

What this application is **not**:

- it is not the operational dashboard of phase 3 (``dashboard/app.py``), which stays
  dedicated to pipeline observability;
- it is not a production portal, and it does not implement authentication or roles;
- it does not expose the test split, and it does not compute generalization metrics
  from a handful of rows: an isolated record produces **predictions**, not quality
  metrics.

Run it locally with::

    uv sync --dev --locked --extra model_lab
    uv run --extra model_lab streamlit run dashboard/app_dev.py --server.address 127.0.0.1
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from credit_monitoring.config import feature_columns, load_config  # noqa: E402
from credit_monitoring.contracts import ContractViolation  # noqa: E402
from credit_monitoring.models import lab  # noqa: E402
from credit_monitoring.models.inference import (  # noqa: E402
    ModelArtifactError,
    compare_models,
    divergence_summary,
    load_model,
)
from credit_monitoring.paths import MODELS_DIR, REPORTS_DIR  # noqa: E402

st.set_page_config(
    page_title="Laboratorio de modelos - Credit Scoring", page_icon="🔬", layout="wide"
)

THRESHOLD = 0.5
EXPERIMENT_ID = "opt-20261026-01"
BATCH_SIZE_LIMIT = 500
PREDICTIONS_FILE = "validation_predictions.csv"

FEATURE_DEFAULTS: dict[str, float] = {
    "LIMIT_BAL": 50_000.0,
    "PAY_0": 0.0,
    "PAY_2": 0.0,
    "PAY_3": 0.0,
    "PAY_4": 0.0,
    "PAY_5": 0.0,
    "PAY_6": 0.0,
    "BILL_AMT1": 20_000.0,
    "BILL_AMT2": 20_000.0,
    "BILL_AMT3": 20_000.0,
    "BILL_AMT4": 20_000.0,
    "BILL_AMT5": 20_000.0,
    "BILL_AMT6": 20_000.0,
    "PAY_AMT1": 2_000.0,
    "PAY_AMT2": 2_000.0,
    "PAY_AMT3": 2_000.0,
    "PAY_AMT4": 2_000.0,
    "PAY_AMT5": 2_000.0,
    "PAY_AMT6": 2_000.0,
}
GOVERNANCE_DEFAULTS: dict[str, float] = {"SEX": 1.0, "EDUCATION": 2.0, "MARRIAGE": 1.0, "AGE": 30.0}


# --------------------------------------------------------------------------- helpers


def _catalog_signature(models_dir: Path, reports_dir: Path) -> tuple:
    """Signature of the artifacts on disk, used as the cache key."""
    signature: list[tuple[str, float, int]] = []
    for root in (models_dir, reports_dir):
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in {".json", ".joblib", ".csv"}:
                stat = path.stat()
                signature.append((str(path), stat.st_mtime, stat.st_size))
    return tuple(signature)


@st.cache_resource(show_spinner=False)
def _catalog(
    models_dir: str, reports_dir: str, experiment_id: str, signature: tuple
) -> lab.Catalog:
    """Build the catalog once per session; the signature invalidates it."""
    config = load_config()
    return lab.discover(
        models_dir=models_dir,
        reports_dir=reports_dir,
        experiment_id=experiment_id,
        features=feature_columns(config),
    )


def _load_published_predictions(models_dir: Path, experiment_id: str) -> pd.DataFrame | None:
    """Probabilities and labels of the frozen validation round, when available."""
    path = models_dir / "optimization" / experiment_id / "selection" / PREDICTIONS_FILE
    if not path.is_file():
        return None
    try:
        return pd.read_csv(path)
    except (OSError, ValueError):
        return None


def synthetic_record(config: dict[str, Any]) -> dict[str, Any]:
    """A synthetic client, used to fill the form. It is not a real record."""
    dataset = config["dataset"]
    record: dict[str, Any] = {dataset["id_column"]: 9_999_999}
    record.update(FEATURE_DEFAULTS)
    record.update(GOVERNANCE_DEFAULTS)
    return record


def build_frame(record: dict[str, Any], config: dict[str, Any]) -> pd.DataFrame:
    """Turn a record into a one-row batch with the canonical columns."""
    dataset = config["dataset"]
    columns = [dataset["id_column"], *feature_columns(config), *dataset["governance_features"]]
    frame = pd.DataFrame([{column: record.get(column) for column in columns}])
    return frame[columns]


def show_dataframe(frame: pd.DataFrame) -> None:
    """Render a table with the width argument supported by the installed Streamlit."""
    try:
        st.dataframe(frame, width="stretch")
    except TypeError:
        st.dataframe(frame, use_container_width=True)


def _signature(selected: list[str], frame: pd.DataFrame) -> str:
    """Signature of a comparison: the models and the batch."""
    payload = json.dumps(
        {
            "models": sorted(selected),
            "rows": int(len(frame)),
            "sha256": hashlib.sha256(frame.to_csv(index=False).encode("utf-8")).hexdigest(),
        },
        sort_keys=True,
    )
    return payload


def store_result(signature: str, payload: dict[str, Any]) -> None:
    """Keep the result of the last explicit comparison in the session."""
    st.session_state["lab_result"] = {"signature": signature, "payload": payload}


def read_result(signature: str) -> dict[str, Any] | None:
    """Return the stored result only when it still matches the current selection."""
    stored = st.session_state.get("lab_result")
    if not stored:
        return None
    return stored["payload"] if stored["signature"] == signature else None


def preset_frames(config: dict[str, Any]) -> dict[str, tuple[pd.DataFrame, str, str]]:
    """Synthetic presets: one valid and four contract violations."""
    base = synthetic_record(config)
    valid = build_frame(base, config)

    duplicated = pd.concat([valid, valid], ignore_index=True)

    non_positive = valid.copy()
    non_positive["LIMIT_BAL"] = 0.0

    out_of_range = valid.copy()
    out_of_range["AGE"] = 150.0

    null_feature = valid.copy()
    null_feature["BILL_AMT1"] = None

    return {
        "valid": (valid, "Lote valido", "O contrato e aceito e o lote e pontuado."),
        "duplicate_id": (
            duplicated,
            "ID duplicado",
            "Viola a regra de identificadores unicos; o lote inteiro e recusado.",
        ),
        "non_positive_limit": (
            non_positive,
            "Limite nao positivo",
            "Viola a regra de LIMIT_BAL positivo; o lote inteiro e recusado.",
        ),
        "age_out_of_range": (
            out_of_range,
            "Idade fora do intervalo",
            "Viola a regra de idade entre 18 e 100 anos; o lote inteiro e recusado.",
        ),
        "null_feature": (
            null_feature,
            "Feature nula",
            "Viola a regra de features obrigatorias sem nulos; o lote inteiro e recusado.",
        ),
    }


# ------------------------------------------------------------------------- rendering


def render_sidebar(catalog: lab.Catalog) -> list[str]:
    """Model selection and traceability."""
    st.sidebar.title("Laboratorio de modelos")
    st.sidebar.caption(
        "Comparacao de artefatos congelados. A aplicacao nao treina, nao promove "
        "modelos e nao altera datasets, metricas oficiais ou o dvc.lock."
    )

    available = catalog.available_models()
    if not available:
        st.sidebar.error("Nenhum artefato de modelo disponivel.")
        return []

    by_key = {entry.key: entry for entry in available}
    default = [entry.key for entry in available if entry.published] or [available[0].key]
    selected = st.sidebar.multiselect(
        "Modelos para comparar",
        options=list(by_key),
        default=default,
        format_func=lambda key: by_key[key].label,
    )

    st.sidebar.subheader("Rastreabilidade")
    for entry in available:
        with st.sidebar.expander(entry.label):
            st.write(f"- Algoritmo: `{entry.algorithm}`")
            st.write(f"- Versao: `{entry.version}`")
            st.write(f"- Papel: `{entry.role}`")
            if entry.candidate_id:
                st.write(f"- candidate_id: `{entry.candidate_id}`")
            if entry.experiment_id:
                st.write(f"- experiment_id: `{entry.experiment_id}`")
            st.write(f"- SHA-256: `{entry.sha256}`")
            st.write(f"- Numero de features: {len(entry.features)}")
            st.write(f"- Limiar: {entry.threshold}")
            st.write(f"- Vigente: {'sim' if entry.published else 'nao'}")

    unavailable = [entry for entry in catalog.models if not entry.available]
    if unavailable:
        st.sidebar.subheader("Artefatos indisponiveis")
        for entry in unavailable:
            st.sidebar.warning(f"{entry.label}: {entry.error}")
    if catalog.errors:
        st.sidebar.subheader("Avisos")
        for message in catalog.errors:
            st.sidebar.warning(message)
    return selected


def render_artifacts(catalog: lab.Catalog) -> None:
    """Readiness of the artifacts."""
    st.subheader("Artefatos e prontidao")
    if not catalog.models:
        st.warning("Nenhum artefato de modelo encontrado.")
        return

    rows = []
    for entry in catalog.models:
        rows.append(
            {
                "modelo": entry.key,
                "algoritmo": entry.algorithm,
                "versao": entry.version,
                "papel": entry.role,
                "vigente": entry.published,
                "sha256": (entry.sha256 or "-")[:16],
                "disponivel": entry.available,
                "observacao": entry.error or "-",
            }
        )
    show_dataframe(pd.DataFrame(rows))

    if catalog.manifest:
        with st.expander("Manifesto da campanha"):
            st.json(
                {
                    "protocol_version": catalog.manifest.get("protocol_version"),
                    "experiment_id": catalog.manifest.get("experiment_id"),
                    "folds": catalog.manifest.get("folds"),
                    "seeds": catalog.manifest.get("seeds"),
                    "budget": catalog.manifest.get("budget"),
                    "criteria": catalog.manifest.get("criteria"),
                    "inputs": catalog.manifest.get("inputs"),
                    "versions": catalog.manifest.get("versions"),
                    "sources": catalog.manifest.get("sources"),
                }
            )
    if catalog.decision:
        with st.expander("Decisao congelada da campanha"):
            st.json(catalog.decision)
    with st.expander("Contrato de dados"):
        config = load_config()
        st.json(
            {
                "contract_version": "1.0.0",
                "regras": config.get("contract", {}),
                "features do modelo": feature_columns(config),
            }
        )


def _metric_rows(catalog: lab.Catalog) -> pd.DataFrame:
    """Side-by-side table of the frozen validation round."""
    comparison = catalog.comparison or {}
    models = comparison.get("models", {})
    incumbent_key = comparison.get("incumbent")
    rows = []
    for key, entry in models.items():
        metrics = entry.get("metrics_unrounded", entry.get("metrics", {}))
        contrast = entry.get("contrast") or {}
        rows.append(
            {
                "modelo": key,
                "papel": entry.get("role"),
                "algoritmo": entry.get("algorithm"),
                "roc_auc": metrics.get("roc_auc"),
                "average_precision": metrics.get("average_precision"),
                "precision": metrics.get("precision"),
                "recall": metrics.get("recall"),
                "f1": metrics.get("f1"),
                "accuracy": metrics.get("accuracy"),
                "brier": metrics.get("brier"),
                "delta_roc_auc_vs_rf_atual": (
                    None if key == incumbent_key else contrast.get("delta")
                ),
                "ic_inferior": None if key == incumbent_key else contrast.get("ci_low"),
                "ic_superior": None if key == incumbent_key else contrast.get("ci_high"),
            }
        )
    return pd.DataFrame(rows)


def render_comparison(catalog: lab.Catalog, models_dir: Path) -> None:
    """Comparison of the models of the frozen validation round."""
    st.subheader("Comparacao dos modelos")
    if not catalog.comparison:
        st.info(
            "Relatorio de comparacao indisponivel: a campanha ainda nao produziu o "
            "relatorio congelado da rodada de validacao."
        )
        return

    comparison = catalog.comparison
    st.caption(
        f"Rodada unica de validacao da campanha {comparison.get('experiment_id')}. "
        f"Metrica primaria: {comparison.get('primary_metric')}; limiar "
        f"{comparison.get('threshold')}. As metricas vem do relatorio congelado: "
        "a aplicacao nao recalcula avaliacoes."
    )

    table = _metric_rows(catalog)
    if not table.empty:
        show_dataframe(table)

    for key, entry in (comparison.get("models") or {}).items():
        matrix = (entry.get("metrics") or {}).get("confusion_matrix") or {}
        contrast = entry.get("contrast") or {}
        with st.expander(f"Matriz de confusao e intervalo - {key}"):
            st.json(
                {
                    "confusion_matrix": matrix,
                    "validation_rows": comparison.get("validation", {}).get("rows"),
                    "validation_positives": comparison.get("validation", {}).get("positives"),
                    "contrast": contrast or None,
                }
            )

    decision = comparison.get("decision") or {}
    st.markdown("**Decisao congelada**")
    st.json(decision)
    st.caption(
        "Os criterios abaixo vem do protocolo pre-declarado; o intervalo e condicional "
        "aos modelos ajustados e a esta validacao."
    )
    for key, result in (comparison.get("criteria") or {}).items():
        with st.expander(f"Criterios - {key}"):
            st.json(result)

    predictions = _load_published_predictions(models_dir, comparison.get("experiment_id") or "")
    if predictions is None:
        st.info("Curvas ROC/PR indisponiveis: as probabilidades da rodada ainda nao foram geradas.")
        return

    st.markdown("**Curvas ROC e PR da rodada**")
    target_column = "target" if "target" in predictions.columns else None
    if target_column is None:
        st.info("Rotulos indisponiveis: as curvas nao podem ser desenhadas.")
        return
    st.pyplot(curves_figure(predictions, comparison.get("models") or {}, target_column))

    st.markdown("**Distribuicao das probabilidades**")
    st.caption(
        "Probabilidade de inadimplencia (classe 1) dos modelos da rodada. A "
        "distribuicao nao substitui a comparacao das metricas."
    )
    distribution = pd.DataFrame(
        {
            key: predictions[key]
            for key in (comparison.get("models") or {})
            if key in predictions.columns
        }
    )
    if not distribution.empty:
        st.pyplot(distribution_figure(distribution))
        show_dataframe(distribution.describe().T)


def curves_figure(
    predictions: pd.DataFrame, models: dict[str, Any], target_column: str
) -> plt.Figure:
    """ROC and precision-recall curves of the frozen validation round.

    The coordinates are unpacked before plotting: ``Axes.plot`` reads a tuple of
    sequences as a two-dimensional dataset and would draw one line per row.
    """
    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    for key in models:
        if key not in predictions.columns:
            continue
        false_positive_rate, true_positive_rate = _roc_curve(
            predictions[target_column], predictions[key]
        )
        recall, precision = _precision_recall_curve(predictions[target_column], predictions[key])
        axes[0].plot(false_positive_rate, true_positive_rate, label=key)
        axes[1].plot(recall, precision, label=key)
    axes[0].plot([0, 1], [0, 1], linestyle="--", color="grey")
    axes[0].set_title("Curva ROC - validacao")
    axes[1].set_title("Curva de precisao-recall - validacao")
    for axis in axes:
        axis.set_xlabel("Falsos positivos")
        axis.legend(loc="lower right")
        axis.grid(alpha=0.3)
    return figure


def distribution_figure(distribution: pd.DataFrame) -> plt.Figure:
    """Histogram of the probabilities of the frozen validation round."""
    figure, axis = plt.subplots(figsize=(10, 4))
    distribution.plot(kind="hist", bins=40, alpha=0.6, ax=axis)
    axis.set_xlabel("Probabilidade de inadimplencia")
    axis.set_ylabel("Registros")
    axis.grid(alpha=0.3)
    return figure


def _roc_curve(target: pd.Series, probability: pd.Series) -> tuple[list[float], list[float]]:
    from sklearn.metrics import roc_curve

    fpr, tpr, _ = roc_curve(target, probability)
    return list(fpr), list(tpr)


def _precision_recall_curve(
    target: pd.Series, probability: pd.Series
) -> tuple[list[float], list[float]]:
    from sklearn.metrics import precision_recall_curve

    precision, recall, _ = precision_recall_curve(target, probability)
    return list(recall), list(precision)


def render_prediction(catalog: lab.Catalog, selected: list[str]) -> None:
    """Single record and batch prediction."""
    st.subheader("Predicao individual e em lote")
    st.caption(
        "As previsoes usam apenas predict_proba de pipelines congelados, depois da "
        "validacao integral do lote. Um registro isolado produz previsoes, nunca "
        "metricas de generalizacao."
    )
    if not selected:
        st.info("Selecione ao menos um modelo na barra lateral.")
        return

    config = load_config()
    models: dict[str, Any] = {}
    for key in selected:
        entry = catalog.by_key(key)
        if entry is None or not entry.available:
            continue
        try:
            models[key] = load_model(entry.path, expected_sha256=entry.sha256)
        except ModelArtifactError as error:
            st.error(f"{key}: {error}")

    if not models:
        st.warning("Nenhum dos modelos selecionados esta disponivel.")
        return

    features = feature_columns(config)
    tab_single, tab_batch = st.tabs(["Registro individual", "Lote CSV"])

    with tab_single:
        columns = st.columns(4)
        values: dict[str, Any] = {}
        with st.form("single-record"):
            record = synthetic_record(config)
            identifier = st.number_input(
                "ID", value=int(record[config["dataset"]["id_column"]]), step=1
            )
            values[config["dataset"]["id_column"]] = identifier
            for index, feature in enumerate(features):
                with columns[index % 4]:
                    values[feature] = st.number_input(
                        feature, value=float(FEATURE_DEFAULTS[feature]), format="%.2f"
                    )
            governance = st.columns(4)
            for index, attribute in enumerate(config["dataset"]["governance_features"]):
                with governance[index % 4]:
                    values[attribute] = st.number_input(
                        attribute, value=float(GOVERNANCE_DEFAULTS[attribute]), format="%.0f"
                    )
            submitted = st.form_submit_button("Pontuar o registro")
        frame = build_frame(values, config)
        signature = _signature(selected, frame)
        if submitted:
            payload = _run_inference(models, frame, config, label="registro individual")
            if payload is not None:
                store_result(signature, payload)
        stored = read_result(signature)
        if stored is not None:
            _render_inference(stored)
        elif st.session_state.get("lab_result"):
            st.warning(
                "O resultado guardado pertence a outra selecao de modelos ou a outro "
                "lote. Refaca a comparacao para ver os numeros atuais."
            )

    with tab_batch:
        st.write(
            "Envie um CSV **sem a coluna de alvo**. O upload e recusado se a coluna de "
            "alvo estiver presente: esta tela e de inferencia, nao de avaliacao."
        )
        upload = st.file_uploader("Lote de inferencia (CSV)", type=["csv"])
        if upload is not None:
            frame = pd.read_csv(upload)
            target_column = config["dataset"]["canonical_target"]
            if target_column in frame.columns:
                st.error(
                    "O lote contem a coluna de alvo. Remova-a: esta tela nao avalia "
                    "modelos e nao aceita lotes rotulados."
                )
            else:
                if len(frame) > BATCH_SIZE_LIMIT:
                    st.warning(
                        f"O lote tem {len(frame)} linhas; o laboratorio processa no "
                        f"maximo {BATCH_SIZE_LIMIT} por chamada."
                    )
                if st.button("Pontuar o lote nos modelos selecionados"):
                    payload = _run_inference(models, frame, config, label="lote")
                    if payload is not None:
                        store_result(_signature(selected, frame), payload)


def _run_inference(
    models: dict[str, Any], frame: pd.DataFrame, config: dict[str, Any], *, label: str
) -> dict[str, Any] | None:
    """Validate the batch and score it with every selected model."""
    try:
        comparison = compare_models(models, frame, config, threshold=THRESHOLD)
    except ContractViolation as violation:
        st.error(f"Lote recusado pelo contrato: {violation.rejected_rows} linhas.")
        st.json(violation.to_dict())
        return None
    except ModelArtifactError as error:
        st.error(str(error))
        return None

    payload = {
        "label": label,
        "comparison": comparison,
        "divergence": divergence_summary(comparison),
    }
    _render_inference(payload)
    return payload


def _render_inference(payload: dict[str, Any]) -> None:
    """Render the outcome of a comparison."""
    comparison = payload["comparison"]
    rows = []
    for key, result in comparison["results"].items():
        rows.append(
            {
                "modelo": key,
                "linhas": result.rows,
                "probabilidade_media": float(result.probability.mean()),
                "positivos_previstos": int(result.predicted.sum()),
                "duracao_local_s": round(result.duration_s, 6),
            }
        )
    show_dataframe(pd.DataFrame(rows))
    st.caption(
        "A duracao e o tempo local de inferencia do lote nesta maquina; nao e uma "
        "metrica de qualidade do modelo."
    )

    divergence = payload["divergence"]
    if divergence["pairs"]:
        st.markdown("**Divergencias entre os modelos**")
        show_dataframe(pd.DataFrame(divergence["pairs"]))

    if comparison["rows"] == 1:
        st.info(
            "Um registro isolado produz apenas previsoes. ROC-AUC, F1 e demais "
            "metricas de generalizacao nao sao calculaveis aqui."
        )
    preview = pd.DataFrame(
        {key: comparison["probabilities"][key] for key in comparison["probabilities"]}
    )
    first = models_key(comparison)[0]
    preview.insert(0, "classe_no_limiar_0.5", comparison["predictions"][first])
    show_dataframe(preview.head(50))


def models_key(comparison: dict[str, Any]) -> list[str]:
    """Keys of the models present in a comparison payload."""
    return list(comparison["probabilities"])


def render_contract(catalog: lab.Catalog, selected: list[str]) -> None:
    """Synthetic contract scenarios."""
    st.subheader("Cenarios de contrato")
    st.caption(
        "Predefinicoes sinteticas locais. Um lote invalido e recusado por inteiro e "
        "produz zero chamadas a qualquer modelo."
    )
    config = load_config()
    models: dict[str, Any] = {}
    for key in selected:
        entry = catalog.by_key(key)
        if entry is None or not entry.available:
            continue
        try:
            models[key] = load_model(entry.path, expected_sha256=entry.sha256)
        except ModelArtifactError:
            continue

    presets = preset_frames(config)
    for _key, (frame, title, expectation) in presets.items():
        with st.expander(f"{title} - esperado: {expectation}"):
            st.write(frame.to_string(index=False))
            try:
                validate = compare_models(models, frame, config)
                st.success(f"Aceito: {validate['rows']} linhas.")
            except ContractViolation as violation:
                st.error(f"Recusado: {violation.rejected_rows} linhas.")
                st.json(violation.to_dict())


def main() -> None:
    """Entry point of the laboratory."""
    st.title("Laboratorio de modelos - Credit Scoring")
    models_dir = Path(MODELS_DIR)
    reports_dir = Path(REPORTS_DIR)
    signature = _catalog_signature(models_dir, reports_dir)
    catalog = _catalog(str(models_dir), str(reports_dir), EXPERIMENT_ID, signature)
    st.caption(
        "Artefatos de "
        f"{len(catalog.available_models())} modelo(s) disponivel(is); "
        f"campanha {EXPERIMENT_ID}. Catalogo recalculado quando os artefatos mudam."
    )

    selected = render_sidebar(catalog)
    tabs = st.tabs(
        ["Artefatos e prontidao", "Comparacao dos modelos", "Predicao", "Cenarios de contrato"]
    )
    with tabs[0]:
        render_artifacts(catalog)
    with tabs[1]:
        render_comparison(catalog, models_dir)
    with tabs[2]:
        render_prediction(catalog, selected)
    with tabs[3]:
        render_contract(catalog, selected)


if __name__ == "__main__":
    main()
