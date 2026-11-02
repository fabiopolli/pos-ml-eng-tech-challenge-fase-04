# Lotes de produção simulados

O cenário `v1.0.2` é gerado pelo estágio DVC `simulate_production` em
`data/production/v1.0.2/`: cópia original das features de validação sem alvo e cópia modificada em
`LIMIT_BAL` e `PAY_AMT1`. Preserva tamanho, ordem e IDs entre cenários; nenhum ID é compartilhado
com a referência (treino). O teste não é usado.

A validação já participou da seleção, portanto produção não é novo holdout de desempenho.
Preservar ID e atributos de governança para o contrato, sem incluí-los na entrada do modelo;
alvo não é necessário à inferência nem aos testes de Data Drift.

Não adicionar os arquivos diretamente ao Git. Os outputs são rastreados pelo DVC, junto ao
manifesto, parâmetros, seed e hashes. Os objetos `v1.0.1` e `v1.0.2` foram enviados ao remote e
recuperados em cache isolado. As mudanças são sintéticas e não representam observações temporais reais,
Concept Drift ou perda real de desempenho; ver `docs/evidence/fase-2.md`.
