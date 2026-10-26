# Checklist das entregas

Status possíveis: `Pendente`, `Em andamento`, `Em revisão`, `Concluído`.

Os 28 IDs correspondem ao [plano geral](plans/plano-de-trabalho-TC4.md); não definem ordem
obrigatória. Na fase 1, integrar 1.7 antes de 1.4/1.5. Itens sem status explícito estão pendentes;
links de código não significam aceite verificado. Responsável, revisor e datas por ID devem ser
confirmados no GitHub Projects; as frentes iniciais do README não substituem essa atribuição.

## Semana 1 - Validação de dados e contratos

- [ ] **1.1** Configuração inicial e DagsHub - Em revisão - `dvc[s3]` e `xlrd` travados no `uv.lock`; `dvc.lock` regularizado e `dvc status` limpo; remote `dagshub` configurado, 25 objetos enviados e **recuperação provada em checkout/cache separado**; workbook original migrado do Git para o DVC. Aguarda revisão da equipe para `Concluído`. Ver [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.1 e §1.6.1.
- [ ] **1.2** Aquisição e exploração - Em revisão - estágio `acquire` reconstrói o bruto a partir do XLS com hashes conferidos; proveniência (DOI, CC BY 4.0, hashes, parâmetros de leitura) em [`docs/DATASET.md`](DATASET.md); auditoria estrutural (`eda`) separada da exploração supervisionada no treino (`explore`); **exposição prévia do teste declarada** em [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.2.1.
- [ ] **1.3** Preparação e split 70/15/15 - Em revisão - `src/credit_monitoring/data/prepare.py`; auditoria de IDs disjuntos, seed 42, referência = treino por hash, linhas úteis ≥ 5.000 e união das remoções (0 linhas no dado real, caminho de remoção coberto por fixture controlada) em `data/processed/preparation_report.json`.
- [ ] **1.4** Treinamento da Regressão Logística - Em revisão - `src/credit_monitoring/models/train.py`; contrato precede o `fit` (spy com zero chamadas em falha); ROC-AUC de validação 0,714497; convergência e custo local registrados.
- [ ] **1.5** Treinamento do Random Forest - Em revisão - mesmo estágio de treino, mesmas entradas e hashes do baseline; ROC-AUC de validação 0,774103; custo local registrado; não se exige que vença o baseline.
- [ ] **1.6** Seleção, serialização e versionamento - Em revisão - `train` (seleção) e `evaluate` (avaliação final) em estágios separados; desempate explícito pelo baseline sobre métricas não arredondadas; recarga verificada (tolerância 1e-12); metadados completos com limiar, hashes, SHA do código, versão do contrato e exposição declarada; **recuperação remota provada** (hashes conferidos e inferência do modelo recuperado com diferença de 3,33e-16). Aguarda revisão da equipe para `Concluído`.
- [ ] **1.7** Pandera antes do treino/inferência - Em revisão - `src/credit_monitoring/contracts/`; lote válido aceito, 7+ perturbações isoladas rejeitadas com rejeição integral do lote e diagnóstico por regra/coluna/contagem; CLI com saída não zero; evidência em [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.7.

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
