"""Validated, aggregate-only context for the phase-2 HTML report."""

from __future__ import annotations

from html import escape
from typing import Any


def _decimal(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _integer(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _percent(value: float, digits: int = 2) -> str:
    return f"{value * 100:.{digits}f}".replace(".", ",") + "%"


def _signed(value: float, digits: int = 2) -> str:
    sign = "−" if value < 0 else "+"
    return sign + _decimal(abs(value), digits)


def _metric_rows(metrics: dict[str, Any], model_metadata: dict[str, Any]) -> str:
    cv = model_metadata["optimization"]["candidates"]
    candidates = [
        ("logistic_regression", "Regressão logística", "Baseline", "logistic_regression"),
        ("random_forest", "Random Forest", "Modelo vigente", "random_forest"),
        (
            "random_forest_finalist",
            "Random Forest finalista",
            "Finalista — não promovido",
            "random_forest_finalist",
        ),
        (
            "logistic_regression_finalist",
            "Regressão logística finalista",
            "Finalista — não promovido",
            "logistic_regression_finalist",
        ),
    ]
    rows = []
    selected = model_metadata["selected_model"]
    for key, label, role, family in candidates:
        finalist_key = f"{family.removesuffix('_finalist')}_finalist"
        cv_value = (
            cv[finalist_key]["cv_mean_roc_auc"]
            if key.endswith("_finalist")
            else cv[finalist_key]["control_mean_roc_auc"]
        )
        validation_auc = metrics["validation"][key]["roc_auc"]
        selected_class = ' class="selected-model"' if key == selected else ""
        rows.append(
            f'<tr{selected_class}><th scope="row">{escape(label)}</th>'
            f"<td>{escape(role)}</td>"
            f"<td>{_decimal(float(cv_value), 4)}</td>"
            f"<td>{_decimal(float(validation_auc), 4)}</td></tr>"
        )
    return "".join(rows)


def _performance_rows(
    training_metrics: dict[str, Any], test_metrics: dict[str, Any], selected_model: str
) -> str:
    evaluations = [
        ("Validação (seleção)", training_metrics["validation"][selected_model]),
        ("Teste (protocolo congelado)", test_metrics["test"]),
    ]
    rows = []
    for label, metrics in evaluations:
        rows.append(
            f'<tr><th scope="row">{escape(label)}</th>'
            f"<td>{_decimal(float(metrics['roc_auc']), 3)}</td>"
            f"<td>{_decimal(float(metrics['average_precision']), 3)}</td>"
            f"<td>{_decimal(float(metrics['precision']), 3)}</td>"
            f"<td>{_decimal(float(metrics['recall']), 3)}</td>"
            f"<td>{_decimal(float(metrics['f1']), 3)}</td>"
            f"<td>{_decimal(float(metrics['accuracy']), 3)}</td>"
            f"<td>{_decimal(float(metrics['brier']), 3)}</td></tr>"
        )
    return "".join(rows)


def _confusion_rows(
    training_metrics: dict[str, Any], test_metrics: dict[str, Any], selected_model: str
) -> str:
    evaluations = [
        ("Validação", training_metrics["validation"][selected_model]),
        ("Teste", test_metrics["test"]),
    ]
    rows = []
    for label, metrics in evaluations:
        matrix = metrics["confusion_matrix"]
        rows.append(
            f'<tr><th scope="row">{label}</th>'
            f"<td>{_integer(matrix['tn'])}</td><td>{_integer(matrix['fp'])}</td>"
            f"<td>{_integer(matrix['fn'])}</td><td>{_integer(matrix['tp'])}</td></tr>"
        )
    return "".join(rows)


def _dataset_section(
    dataset_summary: dict[str, Any], preparation: dict[str, Any], config: dict[str, Any]
) -> str:
    dataset = config["dataset"]
    acquisition = dataset["acquisition"]
    splits = preparation["splits"]
    target_counts = dataset_summary["target_counts"]
    feature_list = "".join(
        f"<code>{escape(feature)}</code> " for feature in dataset["financial_features"]
    )
    split_labels = {"train": "Treino", "validation": "Validação", "test": "Teste"}
    split_rows = []
    for key in ("train", "validation", "test"):
        split = splits[key]
        split_rows.append(
            f'<tr><th scope="row">{split_labels[key]}</th>'
            f"<td>{_integer(split['rows'])}</td>"
            f"<td>{_percent(float(split['target_rate']))}</td></tr>"
        )
    return (
        '<div class="cards">'
        '<article class="metric-card"><span class="metric-label">Base completa</span>'
        f'<strong class="metric-value">{_integer(dataset_summary["rows"])}</strong>'
        f'<span class="metric-note">{_integer(dataset_summary["columns"])} colunas; '
        "sem linhas removidas na preparação</span></article>"
        '<article class="metric-card"><span class="metric-label">Alvo positivo na base</span>'
        f'<strong class="metric-value">{_percent(float(dataset_summary["target_rate"]))}</strong>'
        f'<span class="metric-note">{_integer(int(target_counts["1"]))} de '
        f"{_integer(dataset_summary['rows'])} registros: default no mês seguinte</span></article>"
        '<article class="metric-card"><span class="metric-label">Entradas do modelo</span>'
        f'<strong class="metric-value">{len(dataset["financial_features"])}</strong>'
        '<span class="metric-note">Features financeiras; ID e demografia excluídos</span>'
        "</article></div>"
        '<div class="dataset-grid">'
        '<article class="panel"><h3>Origem e população</h3>'
        f'<p><a href="{escape(acquisition["source_url"], quote=True)}">'
        "UCI Machine Learning Repository, conjunto 350</a>; "
        f'DOI <a href="https://doi.org/{escape(acquisition["doi"], quote=True)}">'
        f"{escape(acquisition['doi'])}</a>.</p>"
        "<p>Dados históricos de clientes de cartão de crédito em Taiwan, de abril a setembro de "
        "2005. Valores monetários em NT$. A licença indicada é "
        f"{escape(acquisition['license'])}.</p>"
        f"<p>Alvo: <code>{escape(dataset['target_column_raw'])}</code>; "
        f"0 = adimplente, 1 = default no mês seguinte."
        f" Fonte: {escape(acquisition['citation'])}</p></article>"
        '<article class="panel"><h3>Divisão e integridade</h3>'
        '<div class="table-scroll"><table><thead><tr><th>Partição</th>'
        "<th>Registros</th><th>Prevalência observada do alvo</th>"
        f"</tr></thead><tbody>{''.join(split_rows)}</tbody></table></div>"
        f"<p>{_integer(preparation['cleaning']['removed_rows'])} linhas removidas; "
        "IDs únicos entre partições e referência idêntica ao treino."
        " A divisão foi estratificada e usa seed 42.</p></article></div>"
        '<details class="technical"><summary>Quais variáveis entram no modelo?</summary>'
        '<div class="feature-list"><p><strong>Financeiras usadas (19):</strong> '
        f"{feature_list}</p><p><strong>Governança fora do modelo:</strong> "
        f"{', '.join(escape(item) for item in dataset['governance_features'])}. "
        f"O identificador <code>{escape(dataset['id_column'])}</code> serve apenas "
        "para auditoria/alinhamento e não é preditor. Excluir demografia, por si só, "
        "não demonstra ausência de viés.</p></div></details>"
    )


def _training_section(
    training_metrics: dict[str, Any],
    test_metrics: dict[str, Any],
    model_metadata: dict[str, Any],
    optimization_manifest: dict[str, Any],
    optimization_comparison: dict[str, Any],
    preparation: dict[str, Any],
) -> str:
    selected = model_metadata["selected_model"]
    selected_label = "Random Forest" if selected == "random_forest" else selected
    selected_parameters = model_metadata["hyperparameters"]
    parameter_labels = {
        "n_estimators": "árvores",
        "max_depth": "profundidade máxima",
        "min_samples_leaf": "mínimo de amostras por folha",
        "min_samples_split": "mínimo para divisão",
        "max_features": "features por divisão",
        "class_weight": "ponderação de classes",
        "C": "regularização C",
        "max_iter": "iterações máximas",
    }
    parameter_text = ", ".join(
        f"{escape(parameter_labels.get(key, key))}: {escape(str(value))}"
        for key, value in selected_parameters.items()
    )
    candidate_rows = _metric_rows(training_metrics, model_metadata)
    performance_rows = _performance_rows(training_metrics, test_metrics, selected)
    confusion_rows = _confusion_rows(training_metrics, test_metrics, selected)
    folds = optimization_manifest["folds"]
    search = optimization_manifest["trial_lists"]
    optimization = model_metadata["optimization"]
    best_finalist_key = max(
        optimization["candidates"],
        key=lambda key: optimization["candidates"][key]["cv_mean_roc_auc"],
    )
    best_finalist = optimization["candidates"][best_finalist_key]
    best_finalist_parameters = model_metadata["candidates"][best_finalist_key]["hyperparameters"]
    finalist_parameter_text = ", ".join(
        f"{escape(parameter_labels.get(key, key))}: {escape(str(value))}"
        for key, value in best_finalist_parameters.items()
    )
    best_label = (
        "Random Forest" if best_finalist["algorithm"] == "random_forest" else "Regressão logística"
    )
    bootstrap = optimization_comparison["models"][best_finalist_key]["contrast"]
    criteria = optimization_comparison["criteria_config"]
    cv_delta = float(best_finalist["cv_mean_roc_auc"] - best_finalist["control_mean_roc_auc"])
    validation_delta = float(
        best_finalist["validation_roc_auc"] - training_metrics["validation"][selected]["roc_auc"]
    )
    decision = optimization_comparison["decision"]["action"]
    decision_label = "manter o modelo vigente" if decision == "keep_current" else decision
    ablation = optimization["ablation"]["random_forest"]
    model_count = len(model_metadata["features"])
    train_rows = preparation["splits"]["train"]["rows"]
    test_exposure = bool(test_metrics.get("test_exposure", {}).get("declared"))
    if not test_exposure:
        raise ValueError("The historical test exposure statement must be explicit in the report")
    return (
        '<div class="cards">'
        '<article class="metric-card"><span class="metric-label">Modelo congelado</span>'
        f'<strong class="metric-value model-name">{escape(selected_label)}</strong>'
        f'<span class="metric-note">{model_count} entradas; limiar de classe '
        f"{_decimal(float(model_metadata['threshold']), 2)}</span></article>"
        '<article class="metric-card"><span class="metric-label">Treino usado na campanha</span>'
        f'<strong class="metric-value">{_integer(train_rows)}</strong>'
        f'<span class="metric-note">CV estratificada em {folds["n_splits"]} folds; '
        f"seed {folds['random_state']}; só treino</span></article>"
        '<article class="metric-card"><span class="metric-label">Resultado da busca</span>'
        f'<strong class="metric-value">{escape(decision_label)}</strong>'
        f'<span class="metric-note">Nenhum finalista cumpriu todos os critérios</span>'
        "</article></div>"
        '<div class="method-grid">'
        '<article class="panel"><h3>Modelos e estratégias</h3>'
        "<p><strong>Regressão Logística:</strong> baseline linear, com padronização, "
        "ponderação balanceada e busca em grade de "
        f"{len(search['logistic_regression'])} combinações.</p>"
        "<p><strong>Random Forest:</strong> modelo de árvores em conjunto; "
        f"{len(search['random_forest'])} configurações amostradas. Parâmetros do modelo mantido: "
        f"{parameter_text}; seed {model_metadata['random_seed']}.</p>"
        f"<p>As buscas foram isoladas do teste e usaram somente as "
        f"{_integer(train_rows)} linhas de treino; a validação foi consultada na rodada final "
        "de comparação. CV e validação são medições em partições diferentes e não devem ser "
        "tratadas como a mesma métrica.</p></article>"
        '<article class="panel"><h3>Resultados de CV e seleção</h3>'
        '<div class="table-scroll"><table><thead><tr><th>Modelo</th><th>Papel</th>'
        "<th>ROC-AUC média CV</th><th>ROC-AUC validação</th>"
        f"</tr></thead><tbody>{candidate_rows}</tbody></table></div>"
        f"<p>Maior CV: {escape(best_label)} finalista, ROC-AUC média "
        f"{_decimal(float(best_finalist['cv_mean_roc_auc']), 4)}. Na validação, "
        f"Δ ROC-AUC vs. vigente = {_signed(validation_delta, 4)}; "
        f"IC pareado de 95% [{_signed(float(bootstrap['ci_low']), 4)}; "
        f"{_signed(float(bootstrap['ci_high']), 4)}]. O intervalo inclui zero.</p>"
        f"<p>Parâmetros desse finalista: {finalist_parameter_text}; "
        f"seed {model_metadata['random_seed']}.</p>"
        "<p>Critérios congelados: ganho de validação ≥ "
        f"{_decimal(float(criteria['min_gain_validation']), 3)}, "
        f"ganho médio CV ≥ {_decimal(float(criteria['min_gain_cv_mean']), 3)} e limite inferior "
        f"do intervalo &gt; 0. O finalista teve Δ CV {_signed(cv_delta, 4)}; a decisão foi "
        "manter o RF vigente, não promover um finalista.</p>"
        "<p>Ablação de razões financeiras não adotada: ganho RF "
        f"{_signed(float(ablation['gain']), 4)} frente ao mínimo de "
        f"{_decimal(float(ablation['min_gain_required']), 3)}.</p></article></div>"
        '<section class="panel performance-panel"><h3>Métricas do modelo vigente (limiar 0,5)</h3>'
        '<div class="table-scroll"><table><thead><tr><th>Avaliação</th><th>ROC-AUC</th>'
        "<th>Average precision</th><th>Precisão</th><th>Recall</th><th>F1</th>"
        f"<th>Acurácia</th><th>Brier</th></tr></thead><tbody>{performance_rows}</tbody></table></div>"
        '<details class="technical"><summary>Matrizes de confusão agregadas</summary>'
        '<div class="table-scroll"><table><thead><tr><th>Avaliação</th><th>TN</th><th>FP</th>'
        f"<th>FN</th><th>TP</th></tr></thead><tbody>{confusion_rows}</tbody></table></div></details>"
        '<details class="technical"><summary>Como ler as métricas</summary>'
        '<div class="feature-list">'
        "<p><strong>ROC-AUC:</strong> capacidade de ordenar casos positivos acima dos negativos; "
        "não é percentual de acerto. <strong>Average precision:</strong> resumo da curva "
        "precisão-recall, informativo com classes desbalanceadas.</p>"
        "<p><strong>Precisão:</strong> proporção de positivos corretos entre previsões classe 1. "
        "<strong>Recall:</strong> proporção dos positivos observados recuperados. "
        "<strong>F1:</strong> "
        "média harmônica de precisão e recall. <strong>Acurácia:</strong> fração total correta. "
        "<strong>Brier:</strong> erro quadrático médio das probabilidades; menor é melhor.</p>"
        "</div></details></section>"
        '<aside class="caution-card"><strong>Limitação da avaliação no teste:</strong> '
        "a análise exploratória histórica calculou relações com o alvo sobre o "
        "arquivo bruto completo, "
        "incluindo registros depois alocados ao teste. O resultado de teste acima é uma avaliação "
        "reproduzível sob o modelo congelado, mas não representa um holdout "
        "historicamente intocado.</aside>"
    )


def build_report_context(
    *,
    dataset_summary: dict[str, Any],
    preparation: dict[str, Any],
    training_metrics: dict[str, Any],
    test_metrics: dict[str, Any],
    model_metadata: dict[str, Any],
    optimization_manifest: dict[str, Any],
    optimization_comparison: dict[str, Any],
    prediction_summary: dict[str, Any],
    config: dict[str, Any],
    comparisons: list[dict[str, Any]],
) -> dict[str, str]:
    """Check provenance consistency, then render aggregate-only report sections."""
    dataset = config["dataset"]
    selected = model_metadata["selected_model"]
    if dataset_summary["rows"] != preparation["cleaning"]["output_rows"]:
        raise ValueError("Dataset audit and preparation row counts differ")
    if dataset_summary["raw_sha256"] != preparation["raw_sha256"]:
        raise ValueError("Dataset audit and preparation source hashes differ")
    if preparation["reference"]["train_sha256"] != model_metadata["train_sha256"]:
        raise ValueError("Prepared training reference and selected model training hashes differ")
    if model_metadata["features"] != dataset["financial_features"]:
        raise ValueError("Selected model features differ from the project configuration")
    if (
        selected != training_metrics["selected_model"]
        or selected != test_metrics["selected_model"]
        or selected != optimization_comparison["decision"]["selected"]
    ):
        raise ValueError("Model selection differs across report source artifacts")
    if model_metadata["model_sha256"] != test_metrics["model_sha256"]:
        raise ValueError("Test metrics do not belong to the selected model hash")
    if float(training_metrics["threshold"]) != float(model_metadata["threshold"]):
        raise ValueError("Validation and selected model classification thresholds differ")
    if float(test_metrics["threshold"]) != float(model_metadata["threshold"]):
        raise ValueError("Test and selected model classification thresholds differ")
    if optimization_manifest["experiment_id"] != model_metadata["optimization"]["experiment_id"]:
        raise ValueError("Optimization manifest and model metadata refer to different campaigns")
    if optimization_manifest["inputs"]["train_sha256"] != model_metadata["train_sha256"]:
        raise ValueError("Optimization campaign and selected model use different training data")
    if not preparation["id_audit"]["coverage_complete"]:
        raise ValueError("Prepared split does not cover the audited source dataset")
    if not all(preparation["id_audit"]["ids_unique_within_split"].values()):
        raise ValueError("Prepared splits contain non-unique IDs")
    if preparation["id_audit"]["id_intersections"]:
        raise ValueError("Prepared splits have overlapping IDs")

    acquisition = dataset["acquisition"]
    target_counts = dataset_summary["target_counts"]
    modified_summary = prediction_summary["predictions"]["modified"]["summary"]
    original_summary = prediction_summary["predictions"]["original"]["summary"]
    if original_summary["rows"] != modified_summary["rows"]:
        raise ValueError("Original and modified production prediction counts differ")
    if original_summary["rows"] != comparisons[0]["current_rows"]:
        raise ValueError("Prediction summary and drift batch row counts differ")

    model_shift = comparisons[1]
    control = comparisons[0]
    alerted = [
        item
        for item in model_shift["features"]
        if item["feature"] in model_shift["drifted_features"]
    ]
    alerted_features = "".join(
        f"<li><code>{escape(item['feature'])}</code>: PSI "
        f"{_decimal(float(item['score']), 3)} &gt; "
        f"{_decimal(float(item['threshold']), 2)}</li>"
        for item in alerted
    )
    mean_delta_pp = (float(modified_summary["mean"]) - float(original_summary["mean"])) * 100
    original_positive_rate = float(original_summary["predicted_positives"]) / int(
        original_summary["rows"]
    )
    modified_positive_rate = float(modified_summary["predicted_positives"]) / int(
        modified_summary["rows"]
    )
    positive_rate_delta_pp = (modified_positive_rate - original_positive_rate) * 100
    predicted_class_delta = int(modified_summary["predicted_positives"]) - int(
        original_summary["predicted_positives"]
    )
    direction = "caiu" if predicted_class_delta < 0 else "subiu"

    dataset_section = _dataset_section(dataset_summary, preparation, config)
    training_section = _training_section(
        training_metrics,
        test_metrics,
        model_metadata,
        optimization_manifest,
        optimization_comparison,
        preparation,
    )
    effect_section = (
        '<div class="cards">'
        '<article class="metric-card"><span class="metric-label">Features com sinal '
        "(referência × modificada)</span>"
        f'<strong class="metric-value">{len(model_shift["drifted_features"])} / '
        f'{len(model_shift["features"])}</strong><span class="metric-note">'
        f"Controle: {control['drifted_feature_count']} sinal(is) em "
        f"{len(control['features'])} features</span></article>"
        '<article class="metric-card"><span class="metric-label">Média do score de default '
        "estimado</span>"
        f'<strong class="metric-value">{_percent(float(original_summary["mean"]))} → '
        f"{_percent(float(modified_summary['mean']))}</strong>"
        f'<span class="metric-note">Variação: '
        f"{_signed(mean_delta_pp, 2)} pontos percentuais</span>"
        "</article>"
        '<article class="metric-card"><span class="metric-label">Previsões classe 1 '
        "no limiar 0,5</span>"
        '<strong class="metric-value">'
        f"{_integer(int(original_summary['predicted_positives']))} → "
        f"{_integer(int(modified_summary['predicted_positives']))}</strong>"
        f'<span class="metric-note">Taxa prevista: {_percent(original_positive_rate)} → '
        f"{_percent(modified_positive_rate)}; variação "
        f"{_signed(positive_rate_delta_pp, 2)} p.p.</span>"
        "</article></div>"
        '<div class="impact-grid"><article class="panel"><h3>O que mudou nas entradas?</h3>'
        f"<p>O controle teve {control['drifted_feature_count']} de {len(control['features'])} "
        f"features acima do limite. Na comparação referência × lote modificado, "
        f"{model_shift['drifted_feature_count']} de {len(model_shift['features'])} sinalizaram:</p>"
        f"<ul>{alerted_features}</ul><p>As outras "
        f"{len(model_shift['features']) - model_shift['drifted_feature_count']} features não "
        "ultrapassaram o limite neste protocolo.</p></article>"
        '<article class="panel"><h3>O que mudou nas saídas do modelo?</h3>'
        f"<p>Com o mesmo modelo congelado e os mesmos {int(original_summary['rows'])} registros, "
        f"a média das probabilidades estimadas deslocou-se {_signed(mean_delta_pp, 2)} pontos "
        f"percentuais. O número de scores acima do limiar de 0,5 {direction} em "
        f"{abs(predicted_class_delta)}"
        ".</p>"
        "<p>Isso quantifica mudança nas <strong>saídas previstas</strong> causada pela entrada "
        "sintética; não quer dizer que houve esse número de defaults a mais/menos."
        "</p></article></div>"
        '<aside class="caution-card"><strong>Conclusão permitida:</strong> o monitor detectou '
        "as mudanças sintéticas declaradas nas distribuições de duas entradas, e a distribuição "
        "dos scores médios moveu-se na direção mostrada acima. "
        "<strong>Conclusão não permitida:</strong> "
        "afirmar que o modelo melhorou ou piorou. Os rótulos foram removidos "
        "dos lotes de produção; "
        "sem eles, não se calcula desempenho pós-drift. PSI das entradas e métricas de desempenho "
        "do classificador medem coisas diferentes e suas magnitudes não são comparáveis.</aside>"
    )
    return {
        "dataset_section": dataset_section,
        "training_section": training_section,
        "effect_section": effect_section,
        "source_sha256": escape(str(dataset_summary["raw_sha256"])),
        "target_rate": _percent(float(dataset_summary["target_rate"])),
        "target_positive_count": _integer(int(target_counts["1"])),
        "target_negative_count": _integer(int(target_counts["0"])),
        "dataset_rows": _integer(int(dataset_summary["rows"])),
        "dataset_columns": _integer(int(dataset_summary["columns"])),
        "dataset_citation": escape(acquisition["citation"]),
        "model_name": escape(selected),
    }
