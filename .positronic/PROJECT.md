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

O código atual faz EDA com relações com o alvo no bruto completo e avalia o teste em cada treino:
registrar exposição prévia e revisar protocolo antes de alegar avaliação intocada. Contrato,
produção/drift e monitoramento ainda dependem de implementação/validação.

## Methods and resources

Python 3.12/uv, Pandas/NumPy, scikit-learn, Pandera, Evidently, DVC, DagsHub Storage, MLflow local,
Streamlit, Pytest/Ruff e GitHub Actions. O remote DagsHub e o extra S3 travado ainda estão
pendentes; consultar `docs/DAGSHUB.md`. Treino e visualização são locais; rede é necessária para
sincronizar objetos, não para treino com cache disponível. Não há orçamento/cota aprovados.

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
IDs/aceites e `git diff --check`. Revisão de planejamento em 2026-10-26 verificou documentação e
código por leitura, sem executar pipeline ou testar acesso remoto DVC; uv não estava disponível.

## Open questions

- Confirmar com a docência a cobertura de Concept Drift, citado no contexto do PDF e não
  detalhado na rubrica. Se necessário, planejar cenário separado com mudança explícita de
  P(y|X) e rótulos sintéticos; não alegar cobertura com testes marginais de features.
- Confirmar datas, disponibilidade e recursos por entrega. A atribuição de responsável/revisor por
  ID foi removida por decisão do operador (2026-10-26): o aceite técnico verificado encerra o ID.
- Concluir remote DagsHub/suporte S3 e teste de recuperação; tratar exposição do teste na revisão
  de EDA/avaliação e fixar métodos/limiares de drift antes da execução de aceite.
