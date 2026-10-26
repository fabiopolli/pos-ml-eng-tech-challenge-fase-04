# Lotes de produção simulados

Planejado: após congelar o modelo, copiar as features da validação para o lote original e gerar
uma cópia modificada em `LIMIT_BAL` e `PAY_AMT1`. Preservar tamanho e IDs entre esses dois
cenários; nenhum ID pode ser compartilhado com a referência (treino). Não usar o teste.

A validação já participou da seleção, portanto produção não é novo holdout de desempenho.
Preservar ID e atributos de governança para o contrato, sem incluí-los na entrada do modelo;
alvo não é necessário à inferência nem aos testes de Data Drift.

Não adicionar os arquivos diretamente ao Git. Versionar os lotes autorizados com DVC/DagsHub,
junto aos parâmetros, seed e hashes necessários à reprodução. A simulação ainda não está
implementada; não interpretar mudanças sintéticas como observações temporais reais.
