# Tech Challenge — Fase 4 | ML Engineering

## Purpose and intended outcome

Solução acadêmica local e reproduzível de credit scoring para demonstrar contratos de dados,
Data Drift, observabilidade e governança em um cenário hipotético de fintech. Não há concessão
real de crédito nem alegação de que drift sintético prova perda real de desempenho.

O plano detalhado e seus aceites estão em `docs/plans/plano-de-trabalho-TC4.md`; o enunciado está
no PDF da mesma pasta. Quatro fases e pesos 25/25/20/15/15 são oficiais; quatro semanas relativas,
28 entregas, dois modelos e a combinação MLflow/Streamlit/DagsHub são escolhas da equipe.
Datas de início/entrega e responsáveis por ID ainda precisam de confirmação.

## Scope and success criteria

- Comparar Regressão Logística e Random Forest na validação, selecionar/congelar o modelo e
  avaliá-lo no teste sem realimentar decisões; serializar artefato e justificativa.
- Contrato Pandera integrado antes do treino/inferência: pelo menos três regras rígidas,
  controles válido/inválidos e rejeição integral de lote operacional inválido.
- Simulação reproduzível em LIMIT_BAL/PAY_AMT1, com controle original e relatório HTML Evidently;
  métodos, intensidades e limiares pré-definidos. Não confundir p-value com limiar de PSI.
- DVC versiona datasets/modelos; GitHub guarda código e metadados, DagsHub Storage guarda objetos.
- MLflow local e Streamlit correlacionam execuções, hashes, métricas, relatórios e alertas;
  demonstrar controle, drift válido, falha de contrato e falha de execução, com recursos locais.
- Governança e causalidade consolidadas no README, reprodução em checkout/cache separado e vídeo
  STAR acessível com até cinco minutos. Código presente não equivale a aceite concluído.

## Research questions and requirements

Dataset UCI 350: 30.000 registros e 23 preditores; 19 variáveis financeiras usadas inicialmente.
ID e atributos demográficos ficam disponíveis para contrato/governança, fora dos preditores.
Preservar origem/conversão XLS/CSV, hashes, atribuição CC BY 4.0 e unidades NT$. Dados históricos
de Taiwan não validam uma população brasileira atual nem passagem de tempo real.

Split estratificado 70/15/15, seed 42 e IDs disjuntos. Referência = cópia intacta do treino.
Após congelar a seleção, features da validação originam produção original/modificada, com os
mesmos IDs entre cenários e sem IDs da referência. Essa reutilização não cria novo holdout de
desempenho. Não usar teste para ajustar modelo, limiares ou simulação. Transformações aprendidas
ajustam-se no treino. Seleção por ROC-AUC; empate favorece baseline; limiar inicial 0.5.

O EDA histórico calculou relações com o alvo no bruto completo, incluindo registros depois
alocados ao teste; essa exposição está declarada em `docs/evidence/fase-1.md`. O estágio `train`
seleciona usando treino e validação e não lê o teste; `evaluate` é um estágio separado, que valida
e avalia no teste o modelo já congelado. Portanto, não descrever o teste como avaliação intocada.
O gate M1 (1.1–1.7) está concluído, incluindo a recuperação DVC verificada em checkout/cache
separado; a extensão 1.6 de otimização e laboratório também está concluída. A fase 2 tem cenário
Data Drift `1.0.2`, inferência, PSI e relatório HTML implementados e verificados. Os objetos DVC
das versões `1.0.1` e `1.0.2` foram publicados/recuperados em cache isolado. Concept Drift não é demonstrado
nesta entrega; por decisão do operador, a docência avaliará o plano após a entrega, sem resposta
prévia como gate de M2. A observabilidade da fase 3 ainda precisa ser concluída.

## Methods and resources

Python 3.12/uv, Pandas/NumPy, scikit-learn, Pandera, Evidently, DVC, DagsHub Storage, MLflow local,
Streamlit, Pytest/Ruff e GitHub Actions. `dvc[s3]` está travado e o remote DagsHub está configurado;
25 objetos foram enviados e a recuperação foi comprovada em checkout/cache separado (evidência em
`docs/evidence/fase-1.md`). O estado local pode não conter todos os objetos: neste checkout,
`uv run dvc status` indicou o workbook da UCI ausente/não materializado, embora referência,
validação e modelo estejam presentes e com hashes conferidos. Consultar `docs/DAGSHUB.md` para
recuperação. Treino e visualização são locais; rede é necessária para sincronizar objetos, não para
treino com cache disponível. As saídas analíticas DVC `1.0.2` foram publicadas e recuperadas em
cache isolado; o relatório acadêmico ampliado em pt-BR (v6) permanece apenas no cache local até
sincronização autorizada. Não há orçamento/cota aprovados.

## Risks and governance

Não adicionar dados/modelos binários diretamente ao Git. Compartilhar via DVC apenas objetos
autorizados e guardar credenciais em configuração local ignorada. Tratar licença, minimização,
viés e retenção desde a aquisição; fase 4 consolida evidências. Apagar ponteiro não remove objeto
do cache/remote. Excluir demografia não garante ausência de viés. Distinguir uso acadêmico da
base legal proposta para a fintech hipotética e hipóteses causais de intervenções sintéticas.

Sem compute remoto, Kubernetes, API em tempo real, serviços de banco/filas dedicados, orquestrador
complexo, AutoML, redes neurais, alertas externos ou retreinamento automático. DagsHub Storage e
SQLite local do MLflow estão no escopo.

## Working conventions

Ler `AGENTS.md`, plano, checklist e arquitetura antes de alterar o projeto. Preservar trabalho
existente; commits semânticos e evidências por ID. Seguir fluxo de branches/revisão do repositório,
respeitando autorizações explícitas do operador. O checklist deve distinguir pendente, em
andamento, em revisão e concluído. Requisitos planejados não são resultados.

## Verification

Ambiente: `uv sync --dev --locked`. Código: `uv run pytest`, `uv run ruff check .` e
`uv run ruff format --check .`. Documentação: links, consistência com enunciado/configuração,
IDs/aceites e `git diff --check`. A evidência de M1 registra execução local e recuperação DVC remota
em clone/cache separado; conferir sempre o estado do checkout atual antes de repetir a DAG ou
sincronizar dados.

## Open questions

- Registrar com clareza que a fase 2 demonstra Data Drift, não Concept Drift; a docência avaliará
  o plano após a entrega, conforme decisão do operador (2026-11-02). Uma expansão posterior exigiria
  mecanismo sintético explícito de mudança em P(y|X), sem alterar rótulos reais.
- Confirmar datas, disponibilidade e recursos por entrega. A atribuição de responsável/revisor por
  ID foi removida por decisão do operador (2026-10-26): o aceite técnico verificado encerra o ID.
- A exposição histórica do teste está declarada; o protocolo distingue seleção/treino de avaliação
  final. Objetos DVC da fase 2 já foram publicados e recuperados em cache isolado.
