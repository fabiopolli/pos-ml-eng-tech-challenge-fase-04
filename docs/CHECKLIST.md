# Checklist das entregas

Status possíveis: `Pendente`, `Em andamento`, `Em revisão`, `Concluído`.

Os 28 IDs correspondem ao [plano geral](plans/plano-de-trabalho-TC4.md); não definem ordem
obrigatória. Na fase 1, integrar 1.7 antes de 1.4/1.5. Itens sem status explícito estão pendentes;
links de código não significam aceite verificado. Responsável, revisor e datas por ID devem ser
confirmados no GitHub Projects; as frentes iniciais do README não substituem essa atribuição.

## Semana 1 - Validação de dados e contratos

- [ ] **1.1** Configuração inicial e DagsHub - Em andamento - estrutura/CI presentes; falta suporte S3 travado, remote e recuperação DVC com cache separado e credenciais locais.
- [ ] **1.2** Aquisição e exploração - Em revisão - `notebooks/01_eda.ipynb`, `src/credit_monitoring/eda.py`, `docs/DATASET.md`; verificar conversão/licença/hashes e restringir análises que orientam modelagem ao treino.
- [ ] **1.3** Preparação e split 70/15/15 - Em revisão - `src/credit_monitoring/data/prepare.py`, `dvc.yaml`; conferir IDs disjuntos, seed e referência = treino.
- [ ] **1.4** Treinamento da Regressão Logística - Em revisão - evidência: `src/credit_monitoring/models/train.py`, `reports/metrics.json`.
- [ ] **1.5** Treinamento do Random Forest - Em revisão - evidência: `src/credit_monitoring/models/train.py`, `reports/metrics.json`.
- [ ] **1.6** Seleção, serialização e versionamento - Em revisão - `reports/metrics.json`, `models/credit_model_metadata.json`; congelar decisões antes do teste, registrar exposições prévias e demonstrar recuperação DVC/DagsHub.
- [ ] **1.7** Pandera antes do treino/inferência; pelo menos três regras, controles válido/inválidos e bloqueio integral, sem limpeza silenciosa de lote operacional.

## Semana 2 - Simulação e detecção de drift

- [ ] **2.1** Referência = treino; produção original = features da validação após seleção; IDs disjuntos entre referência/produção, sem usar o teste.
- [ ] **2.2** Cenário, transformações, métodos/limiares pré-definidos e decisão de cobertura de Concept Drift documentados.
- [ ] **2.3** Simulação reproduzível; cópias original/modificada com mesmos IDs e tamanho, parâmetros/hashes versionados em DVC.
- [ ] **2.4** Contrato e inferência no lote de produção.
- [ ] **2.5** Integração com Evidently.
- [ ] **2.6** Comparações referência/original e referência/modificada; métodos, magnitude e múltiplos testes documentados, sem confundir p-value com PSI.
- [ ] **2.7** HTML Evidently com duas features alteradas detectadas, controle, estatísticas, limiares, versões e interpretação sem alegar perda real de desempenho.

## Semana 3 - Observabilidade

- [ ] **3.1** Logs estruturados de todas as etapas.
- [ ] **3.2** Métricas operacionais, contagens sem duplicação, tempo de CPU e pico de memória com unidades/plataforma.
- [ ] **3.3** Ambiente e experimento MLflow.
- [ ] **3.4** Métricas/artefatos no MLflow por ID de execução, SHA Git, hashes DVC/modelo/dados e configuração.
- [ ] **3.5** Dashboard Streamlit funcional.
- [ ] **3.6** Alertas de contrato, execução e drift.
- [ ] **3.7** Controle, drift válido, falha de contrato e falha de execução demonstrados; dashboard também trata ausência de execuções.

## Semana 4 - Governança e apresentação

- [ ] **4.1** Tratamento e origem dos dados documentados.
- [ ] **4.2** Uso acadêmico versus cenário hipotético de crédito; base legal proposta, retenção/descarte local e remoto, incluindo cópias DVC.
- [ ] **4.3** Governança, rastreabilidade e viés por grupos com denominadores/limitações, sem assumir que excluir demografia elimina viés.
- [ ] **4.4** Hipóteses causais, limites do experimento e ações de investigação/mitigação.
- [ ] **4.5** README consolidado com evidências reais.
- [ ] **4.6** Vídeo STAR de até cinco minutos.
- [ ] **4.7** Reprodução em checkout/cache separado, acesso dos avaliadores aos objetos/relatórios, histórico e cobertura de todos os requisitos, inclusive decisão sobre Concept Drift.
