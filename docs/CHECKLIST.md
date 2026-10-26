# Checklist das entregas

Status possíveis: `Pendente`, `Em andamento`, `Em revisão`, `Concluído`.

Os 28 IDs correspondem ao [plano geral](plans/plano-de-trabalho-TC4.md); não definem ordem
obrigatória. Na fase 1, integrar 1.7 antes de 1.4/1.5. Itens sem status explícito estão pendentes;
links de código não significam aceite verificado. O **grau de prova** de cada entrega da fase 1
(execução original × revalidação independente por execução) está na seção "Grau de evidência por
seção" de [`docs/evidence/fase-1.md`](evidence/fase-1.md).

## Semana 1 - Validação de dados e contratos

- [x] **1.1** Configuração inicial e DagsHub - Concluído - `dvc[s3]` e `xlrd` travados no `uv.lock`; `dvc.lock` regularizado e `dvc status` limpo; remote `dagshub` configurado, 25 objetos enviados e **recuperação provada em checkout/cache separado**; workbook original migrado do Git para o DVC. Ver [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.1 e §1.6.1. **Revalidado por execução** em §1.1.1 (clone novo do GitHub sem cache: instalação travada, recuperação remota do zero, integridade dos hashes e inferência sobre o modelo recuperado); o item ali achado — a reavaliação das dependências de fases futuras — foi **fechado** no mesmo dia: `evidently`, `mlflow`, `streamlit` e `ucimlrepo` passaram para os extras `drift`, `observability` e `provenance`, com o ambiente padrão reduzido de 244 para 170 pacotes.
- [x] **1.2** Aquisição e exploração - Concluído - estágio `acquire` reconstrói o bruto a partir do XLS com hashes conferidos; proveniência (DOI, CC BY 4.0, hashes, parâmetros de leitura) em [`docs/DATASET.md`](DATASET.md); auditoria estrutural (`eda`) separada da exploração supervisionada no treino (`explore`); **exposição prévia do teste declarada** em [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.2.1.
- [x] **1.3** Preparação e split 70/15/15 - Concluído - `src/credit_monitoring/data/prepare.py`; auditoria de IDs disjuntos, seed 42, referência = treino por hash, linhas úteis ≥ 5.000 e união das remoções (0 linhas no dado real, caminho de remoção coberto por fixture controlada) em `data/processed/preparation_report.json`; **revalidada por execução** em [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.3.1, com a falha por IDs compartilhados coberta por teste e o relatório vinculado à impressão digital da configuração, às razões de split e ao arredondamento das taxas.
- [x] **1.4** Treinamento da Regressão Logística - Concluído - `src/credit_monitoring/models/train.py`; contrato precede o `fit` (spy com zero chamadas em falha); ROC-AUC de validação 0,714497; convergência e custo local registrados. **Revalidado por execução** em [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.4.1, com o escopo do `fit` (só o treino) agora provado por teste e por perturbação da validação. **Baseline serializado** como artefato versionado (`models/candidates/`), com hash nos metadados (§1.5.2).
- [x] **1.5** Treinamento do Random Forest - Concluído - mesmo estágio de treino, mesmas entradas e hashes do baseline; ROC-AUC de validação 0,774103; custo local registrado; não se exige que vença o baseline. **Revalidado por execução** em §1.5.1, com a recalculabilidade das métricas e a soma da matriz de confusão agora provadas por teste. **Todos os candidatos serializados** e auditáveis por artefato (§1.5.2), sem avaliar o baseline no teste.
- [x] **1.6** Seleção, serialização e versionamento - Concluído - `train` (seleção) e `evaluate` (avaliação final) em estágios separados; desempate explícito pelo baseline sobre métricas não arredondadas; recarga verificada (tolerância 1e-12); metadados completos com limiar, hashes, SHA do código, versão do contrato e exposição declarada; **recuperação remota provada** (hashes conferidos e inferência do modelo recuperado com diferença de 3,33e-16). **Caminho local revalidado por execução** em §1.6.2.
- [x] **1.7** Pandera antes do treino/inferência - Concluído - `src/credit_monitoring/contracts/`; lote válido aceito, 7+ perturbações isoladas rejeitadas com rejeição integral do lote e diagnóstico por regra/coluna/contagem; CLI com saída não zero; evidência em [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.7; **revalidada por execução** em §1.7.1, com o spy de predição (zero chamadas em falha) e a prova de validação do lote integral antes da seleção das 19 entradas agora automatizadas e verificadas por mutação.

## Extensão do plano 1.6 — campanha de otimização dos modelos

Extensão **planejada** por Bill Kopp, sem criar uma quinta fase e sem substituir o aceite
histórico de M1. Detalhes em [`docs/plans/1.6-otimizacao-modelos.md`](plans/1.6-otimizacao-modelos.md);
evidência em [`docs/evidence/1.6-otimizacao-modelos.md`](evidence/1.6-otimizacao-modelos.md).

- [x] **1.6-O1** Protocolo e preservação - Concluído - `configs/optimization.yaml` congela folds, sementes, orçamento, critérios e espaços de busca; manifesto com hashes, versões, fontes e lista efetiva de trials gravado em `reports/optimization/<exp>/tuning/manifest.json` antes de qualquer resultado.
- [x] **1.6-O2** Busca no treino - Concluído - `src/credit_monitoring/models/tune.py` lê **somente** `train.csv`; controles, 24 configurações de RF e 12 de LR nos mesmos cinco folds, com pré-processamento ajustado dentro dos folds; falhas registradas, nunca convertidas em score zero.
- [x] **1.6-O3** Ablação e finalistas - Concluído - uma única variante de razões financeiras por família (`src/credit_monitoring/models/features.py`), repetição do RF com as sementes 17 e 73 sem escolher a melhor, e um finalista congelado por algoritmo.
- [x] **1.6-O4** Seleção e promoção - Concluído - rodada única de validação com o RF vigente e os dois finalistas, bootstrap pareado e estratificado (2.000 reamostragens, seed 42, intervalo de 97,5% por contraste), decisão explícita `promote` ou `keep_current` em `reports/optimization/<exp>/selection/comparison.json`, sem acesso ao teste.
- [x] **1.6-O5** Congelamento e transferência - Concluído - decisão integrada ao estágio de seleção (`src/credit_monitoring/models/train.py`): artefato publicado, metadados estendidos (algoritmo e versão candidata separados), incumbente arquivado e recarregado com paridade de probabilidades, `dvc.lock` coerente e sem dois donos para a mesma saída.
- [x] **1.6-O6** Laboratório de modelos - Concluído - `dashboard/app_dev.py` (Streamlit, extra `model_lab`) com artefatos e prontidão, comparação lado a lado com curvas ROC/PR, predição individual e em lote e cenários de contrato; serviço de inferência compartilhado em `src/credit_monitoring/models/inference.py`; testes com `streamlit.testing.v1.AppTest` e `dashboard/README.md`. Inspeção visual em navegador local registrada na evidência (§11.3), com o defeito de renderização encontrado e corrigido durante a inspeção (§11.4) e teste de regressão correspondente.

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
