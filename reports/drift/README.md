# Relatórios de drift

Relatório HTML de Data Drift e resumos estatísticos agregados, sem registros individuais.

- `results-v1.0.2.json`: resumo agregado versionado no Git e consistente com o manifesto/protocolo.
- `prediction_summary-v1.0.2.json`: resumo agregado DVC usado como dependência do estágio de
  detecção; probabilidades persistidas têm precisão fixa de 12 casas, sem caminhos locais ou duração.
- `phase-2-drift-v1.0.2-ptbr-v6.html`: relatório em português brasileiro com origem/splits do
  dataset, target/prevalência, estratégia e modelos, CV/validação/teste separados, seleção com
  incerteza, PSI por feature e mudança agregada nos scores e classes previstos. Usa a métrica de
  contagem de linhas do Evidently; o detector PSI canônico continua sendo a implementação
  customizada registrada no JSON.

Use os nomes versionados. Saídas intermediárias não versionadas do mesmo cenário não são fonte
autoritativa. Os dados e resultados analíticos da revisão `1.0.2` foram enviados/recuperados; a
revisão de apresentação `ptbr-v6` foi gerada localmente e ainda precisa ser sincronizada ao DagsHub.
A revisão de dados `1.0.2` persiste probabilidades a 12 casas e elimina a variação de ponto
flutuante inferior a `3.4e-16`.
