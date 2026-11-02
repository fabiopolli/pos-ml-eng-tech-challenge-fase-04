# Relatórios de drift

Relatórios HTML do Evidently e resumos estatísticos, sem registros individuais.

- `results-v1.0.2.json`: resumo agregado versionado no Git e consistente com o manifesto/protocolo.
- `prediction_summary-v1.0.2.json`: resumo agregado DVC usado como dependência do estágio de
  detecção; probabilidades persistidas têm precisão fixa de 12 casas, sem caminhos locais ou duração.
- `phase-2-drift-v1.0.2-final.html`: relatório Evidently dos artefatos reproduzíveis e precisão
  registrada.

Use os nomes versionados. Saídas intermediárias não versionadas do mesmo cenário não são fonte
autoritativa. Versão `1.0.1` e revisão `1.0.2` foram enviadas/recuperadas. A revisão `1.0.2`
persiste probabilidades a 12 casas e elimina a variação de ponto flutuante inferior a `3.4e-16`.
