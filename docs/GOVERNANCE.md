# Governança e LGPD

> Documento inicial. Controles começam na aquisição; consolidar evidências reais na fase 4 e
> apresentar a governança e a análise causal no README, como exige o enunciado.

## Origem e finalidade

- Dataset: UCI Default of Credit Card Clients (ID 350).
- Finalidade acadêmica: estudar risco de inadimplência e monitoramento de degradação.
- O sistema não toma decisões reais de crédito. A UCI descreve dados de clientes em Taiwan;
  não presumir ausência de risco de reidentificação apenas por ser um dataset público.
- A página da UCI indica CC BY 4.0: preservar atribuição e descrição das conversões/transformações.
  Fonte consultada em 2026-10-26: [UCI 350](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients),
  DOI [10.24432/C55S3H](https://doi.org/10.24432/C55S3H).
- Datasets e modelos aprovados para compartilhamento serão armazenados no DagsHub Storage via DVC;
  confirmar termos de uso da fonte e autorização antes do primeiro envio remoto.
- Tokens do DagsHub e credenciais do remote devem permanecer em configuração local não versionada.

## Inventário e minimização

Documentar as variáveis pessoais/demográficas, as 19 features financeiras usadas no modelo e a
justificativa para excluir atributos demográficos da predição inicial. Avaliações de viés podem
usar esses atributos de forma controlada e agregada, com tamanho dos grupos, denominadores e
limitações. A exclusão de atributos demográficos não elimina proxies nem garante ausência de viés.
O identificador técnico do dataset não deve ser apresentado como identidade civil do cliente;
distinguir dados pessoais/PII de categorias sensíveis definidas em lei.

## Pontos a concluir

- distinguir uso acadêmico/licença da proposta de base legal para crédito na fintech hipotética;
- transparência e possibilidade de contestação da decisão;
- controles de acesso e segregação de ambientes;
- retenção, descarte e rastreabilidade em cache DVC, objetos DagsHub, Git e MLflow; apagar um
  ponteiro não apaga objetos remotos, e exclusão de cache/versões requer decisão explícita;
- avaliação de viés por grupos relevantes;
- riscos, limitações e supervisão humana;
- resposta a drift e critérios para suspensão/revisão do modelo;
- análise causal: intervenções sintéticas são conhecidas por construção; inflação ou novos perfis
  são hipóteses de contexto, não causas identificadas pelo teste de drift;
- cobertura da menção a Concept Drift no enunciado, sem confundi-lo com mudança marginal de features.
