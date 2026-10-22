"""Initial Streamlit shell for the observability dashboard."""

import streamlit as st

st.set_page_config(page_title="Credit Monitoring", page_icon="📊", layout="wide")
st.title("Credit Scoring - Observabilidade")
st.info(
    "Fundação do dashboard criada. As métricas de execução, qualidade e drift serão "
    "conectadas na Etapa 3."
)

pipeline, model, alerts = st.columns(3)
pipeline.metric("Status do pipeline", "Aguardando execução")
model.metric("Features com drift", "-")
alerts.metric("Alertas ativos", "-")
