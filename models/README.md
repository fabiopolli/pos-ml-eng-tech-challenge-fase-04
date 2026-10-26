# Modelos

Saídas do estágio `train`:

- `credit_model.joblib` — o modelo **selecionado**, congelado. É a única entrada do estágio
  `evaluate`, que recusa qualquer artefato cujo hash não corresponda ao registrado na seleção.
- `candidates/credit_model_<candidato>.joblib` — **cada candidato** ajustado, inclusive o
  selecionado, para que a comparação entre os modelos seja auditável a partir de artefatos, sem
  retreinar. Os hashes, hiperparâmetros, convergência e a marca de selecionado ficam no bloco
  `candidates` de `credit_model_metadata.json`.
- `credit_model_metadata.json` — features, hiperparâmetros, hashes dos dados e versões, seleção,
  limiar, versão do contrato, exposição do teste e recarga verificada.

Todos os arquivos são rastreados pelo DVC e ignorados pelo Git. Métricas em
`reports/metrics.json`; o registro no MLflow é uma etapa futura.

O baseline permanece restrito ao conjunto de validação: o estágio `evaluate` não pontua candidatos
no conjunto de teste.
