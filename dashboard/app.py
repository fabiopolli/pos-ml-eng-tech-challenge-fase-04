"""Read-only operational dashboard for Phase 3."""

import hashlib

import streamlit as st

from credit_monitoring.monitoring.run_store import load_records, local_root

STATUS_LABELS = {
    "succeeded": "Concluída",
    "rejected": "Rejeitada",
    "failed": "Falhou",
    "running": "Em curso ou interrompida",
}


def display(value, unit=""):
    if value is None:
        return "Indisponível"
    return f"{value:.3f}{unit}" if isinstance(value, float) else f"{value}{unit}"


def main():
    st.set_page_config(page_title="Credit Scoring | Operações", layout="wide")
    st.title("Credit Scoring · Operações")
    st.button("Atualizar execuções")
    root = local_root()
    records, incompatible = load_records(root)
    if incompatible:
        st.warning(f"{incompatible} registro(s) ilegível(is) ou com versão incompatível.")
    if not records:
        st.info("Nenhuma execução registrada. As métricas estão indisponíveis.")
        return
    latest = records[0]
    last_ok = next((item for item in records if item["status"] == "succeeded"), None)
    st.caption(f"Última tentativa · {STATUS_LABELS[latest['status']]} · {latest['started_at']}")
    st.caption(
        f"Última bem-sucedida · {last_ok['started_at']} · {last_ok['execution_id']}"
        if last_ok
        else "Última bem-sucedida · Indisponível"
    )
    by_id = {item["execution_id"]: item for item in records}
    execution_id = st.selectbox(
        "Execução",
        list(by_id),
        format_func=lambda key: f"{by_id[key]['scenario']} · {by_id[key]['started_at']} · {key}",
    )
    record = by_id[execution_id]
    tracking = record["tracking"]
    if tracking["status"] == "recorded" and (root / "mlflow.db").is_file():
        st.caption(f"MLflow · run {tracking['run_id']}")
    else:
        st.warning("Registro no MLflow indisponível. Exibindo o histórico local.")

    st.subheader("Saúde da execução")
    status, duration, cpu, memory = st.columns(4)
    resources = record["resources"]
    status.metric("Estado", STATUS_LABELS[record["status"]])
    duration.metric("Duração", display(resources.get("wall_time_s"), " s"))
    cpu.metric("CPU", display(resources.get("cpu_time_s"), " s"))
    memory.metric("Pico de memória", display(resources.get("process_peak_rss_mib"), " MiB"))
    st.caption(f"{resources.get('platform', '')} · {resources.get('scope', '')}")
    if record.get("reason"):
        st.write(f"{record.get('stage') or 'Execução'} · {record['reason']}")
    for column, (key, label) in zip(
        st.columns(4),
        (
            ("input_rows", "Entrada"),
            ("accepted_rows", "Aprovados"),
            ("rejected_rows", "Rejeitados"),
            ("inferred_rows", "Inferidos"),
        ),
        strict=True,
    ):
        column.metric(label, display(record["counts"].get(key)))
    with st.expander("Etapas e rastreabilidade"):
        st.json({"stages": record.get("stages", {}), **record["provenance"]})

    st.subheader("Alertas")
    st.caption(f"{len(record['alerts'])} ocorrência(s) nesta execução")
    for alert in record["alerts"]:
        show = st.error if alert["severity"] == "error" else st.warning
        feature = f" · {alert['feature']}" if "feature" in alert else ""
        show(f"{alert['type']}{feature} · {alert['message']}")
        if alert.get("diagnostics"):
            st.dataframe(alert["diagnostics"]["failed_rules"], hide_index=True)

    st.subheader("Modelo e distribuição de scores")
    st.write(f"Versão · {record['provenance'].get('model_version', 'Indisponível')}")
    metrics = record["model_metrics"]
    if metrics:
        for key, label in (("validation", "Validação"), ("test", "Teste congelado")):
            st.caption(f"{label} · {metrics[key + '_source']}")
            st.json(metrics[key], expanded=False)
        if metrics.get("test_exposure"):
            st.caption("A avaliação congelada tem exposição histórica do teste documentada.")
    inference = record.get("inference")
    if inference:
        st.write(f"Probabilidade média · {display(inference['mean'])}")
        histogram = inference["histogram"]
        labels = [
            f"{left:.1f}–{right:.1f}"
            for left, right in zip(histogram["edges"], histogram["edges"][1:], strict=False)
        ]
        st.bar_chart(dict(faixa=labels, registros=histogram["counts"]), x="faixa", y="registros")
    else:
        st.info("Distribuição indisponível.")

    st.subheader("Data Drift")
    drift = record.get("drift")
    if not drift:
        st.info("Drift não avaliado nesta tentativa.")
        return
    st.write(f"{drift['comparison_id']} · {drift['drifted_feature_count']} feature(s) com drift")
    st.caption("Resultado do protocolo congelado M2. O PSI mede mudança de distribuição.")
    st.dataframe(
        [
            {key: row[key] for key in ("feature", "method", "score", "threshold", "drift")}
            for row in drift["features"]
        ],
        hide_index=True,
    )
    directory = (root / "runs" / execution_id).resolve()
    html = (directory / "drift.html").resolve()
    if directory.is_relative_to(root) and html.parent == directory and html.is_file():
        try:
            payload = html.read_bytes()
            if hashlib.sha256(payload).hexdigest() == record["provenance"].get("html_sha256"):
                st.download_button("Baixar relatório de drift", payload, "drift.html", "text/html")
                return
        except OSError:
            pass
    st.caption("HTML compatível indisponível.")


main()
