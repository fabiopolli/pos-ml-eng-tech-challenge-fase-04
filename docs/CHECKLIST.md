# Checklist das entregas

Status possíveis: `Pendente`, `Em andamento`, `Em revisão`, `Concluído`.

## Semana 1 - Validação de dados e contratos

- [x] **1.1** Configuração inicial do repositório - evidência: estrutura, `pyproject.toml` e CI.
- [ ] **1.2** Aquisição e exploração do dataset - Em revisão - evidência: `notebooks/01_eda.ipynb`, `src/credit_monitoring/eda.py`, `docs/DATASET.md`.
- [ ] **1.3** Preparação e split estratificado 70/15/15 - Em revisão - evidência: `src/credit_monitoring/data/prepare.py`, `dvc.yaml`.
- [ ] **1.4** Treinamento da Regressão Logística - Em revisão - evidência: `src/credit_monitoring/models/train.py`, `reports/metrics.json`.
- [ ] **1.5** Treinamento do Random Forest - Em revisão - evidência: `src/credit_monitoring/models/train.py`, `reports/metrics.json`.
- [ ] **1.6** Avaliação, seleção e serialização do modelo - Em revisão - evidência: `reports/metrics.json`, `models/credit_model_metadata.json`.
- [ ] **1.7** Data Contract Pandera e lote inválido rejeitado.

## Semana 2 - Simulação e detecção de drift

- [ ] **2.1** Datasets de referência e produção separados.
- [ ] **2.2** Cenário de drift documentado.
- [ ] **2.3** Script reproduzível de simulação.
- [ ] **2.4** Contrato e inferência no lote de produção.
- [ ] **2.5** Integração com Evidently.
- [ ] **2.6** Testes estatísticos e limiares documentados.
- [ ] **2.7** Relatório HTML de drift.

## Semana 3 - Observabilidade

- [ ] **3.1** Logs estruturados de todas as etapas.
- [ ] **3.2** Métricas operacionais.
- [ ] **3.3** Ambiente e experimento MLflow.
- [ ] **3.4** Métricas e artefatos registrados no MLflow.
- [ ] **3.5** Dashboard Streamlit funcional.
- [ ] **3.6** Alertas de contrato, execução e drift.
- [ ] **3.7** Cenários normal e de falha demonstrados.

## Semana 4 - Governança e apresentação

- [ ] **4.1** Tratamento e origem dos dados documentados.
- [ ] **4.2** Plano LGPD, retenção e descarte.
- [ ] **4.3** Governança, rastreabilidade e riscos do modelo.
- [ ] **4.4** Análise causal e estratégias de mitigação.
- [ ] **4.5** README consolidado com evidências reais.
- [ ] **4.6** Vídeo STAR de até cinco minutos.
- [ ] **4.7** Revisão final de código, evidências e histórico.

