# DagsHub: versionamento remoto com DVC

## Papel no projeto

DagsHub Storage será o remote de objetos do DVC para armazenar datasets e artefatos do pipeline,
incluindo o modelo produzido pelo estágio `train`. O GitHub continua sendo o remoto canônico de
código e documentação. Arquivos ponteiro `.dvc`, `dvc.yaml`, `dvc.lock` e configurações não
secretas do DVC são versionados no Git; conteúdos grandes ficam no remote DagsHub Storage.

A partir da fase 1, o **workbook original da UCI também é um objeto DVC**
(`data/default of credit card clients.xls.dvc`): ele saiu do histórico do Git e passou a ser
versionado pelo DVC. Consequência direta: **um clone novo só reproduz o pipeline depois de
`uv run dvc pull -r dagshub`**, porque a fonte do bruto não está mais no repositório Git.
Enquanto o remote não estiver configurado, a única cópia do XLS está no cache local do DVC.

O repositório já rastreia o CSV bruto e declara os datasets preparados e modelos como saídas DVC.
No estado atual, `.dvc/config` ainda não define um remote. A integração só estará ativa depois que
o projeto GitHub for conectado/importado no DagsHub e as credenciais forem configuradas localmente.

O endpoint S3 abaixo exige suporte S3 no DVC. A dependência atual `dvc[s3]>=3,<4` está declarada
e travada no `uv.lock` desde a fase 1, junto com `xlrd` (leitura de `.xls`) usada pelo estágio
`acquire`. Com uv disponível, o comando de manutenção é `uv add --dev 'dvc[s3]>=3,<4'`. Depois
dessa alteração versionada, cada integrante instala o mesmo ambiente com `uv sync --dev --locked`.

## Configuração inicial (por integrante)

1. Conectar o repositório GitHub existente ao DagsHub seguindo o
   [guia oficial de conexão](https://dagshub.com/docs/quick_start/connect_existing_project/).
2. Na página do repositório DagsHub, abrir a opção de configuração de DVC Storage e copiar os
   valores exibidos para o remote daquele repositório. Não presumir owner, slug, endpoint ou token.
3. Preencher as credenciais no `.env` local (**não versionado**):

   ```bash
   cp .env.example .env
   $EDITOR .env   # preencher DAGSHUB_OWNER, DAGSHUB_REPO e DAGSHUB_TOKEN
   ```

   O DagsHub entrega **um único token** para o DVC Storage (aba *Data → DVC* do repositório), e
   o mesmo token vai nos dois campos de credencial, como no guia oficial. Se a página mostrar um
   par de chaves, use o valor de **secret/token** nos dois campos: o gateway do DagsHub autentica
   pelo `access_key_id` e rejeita com `401 Unauthorized` um valor diferente do token. Se colar a
   URL completa do repositório em `DAGSHUB_REPO`, o script extrai o slug.

4. Aplicar a configuração com o script, que grava as credenciais em `.dvc/config.local` (ignorado
   pelo Git) e nunca imprime os valores:

   ```bash
   scripts/configure_dagshub.sh
   ```

   O script é equivalente ao procedimento manual descrito abaixo e falha com mensagem explícita
   quando alguma variável está vazia.

### Procedimento manual equivalente

```bash
DAGSHUB_OWNER='owner-do-repositorio'
DAGSHUB_REPO='nome-do-repositorio'
uv run dvc remote add -d dagshub s3://dvc
uv run dvc remote modify dagshub endpointurl "https://dagshub.com/${DAGSHUB_OWNER}/${DAGSHUB_REPO}.s3"
```

Se o remote já existir, atualize-o em vez de tentar criá-lo novamente:

```bash
uv run dvc remote modify dagshub url s3://dvc
uv run dvc remote modify dagshub endpointurl "https://dagshub.com/${DAGSHUB_OWNER}/${DAGSHUB_REPO}.s3"
uv run dvc remote default dagshub
```

Armazenar `access_key_id` e `secret_access_key` localmente, com os valores/token fornecidos pelo
DagsHub. O `--local` grava em `.dvc/config.local`, que não deve ser commitado:

```bash
read -rsp 'DagsHub token: ' DAGSHUB_TOKEN; printf '\n'
uv run dvc remote modify dagshub --local access_key_id "$DAGSHUB_TOKEN"
uv run dvc remote modify dagshub --local secret_access_key "$DAGSHUB_TOKEN"
unset DAGSHUB_TOKEN
```

Nunca passe tokens em commits, `.env.example`, documentação, logs ou configuração DVC
compartilhada. As linhas `read` solicitam os valores sem exibi-los nem incluí-los no histórico
do shell.

## Sincronizar dados e modelos

Após adicionar/atualizar os objetos DVC e commitar localmente seus ponteiros/`dvc.lock`, enviar os
objetos antes de publicar o commit Git correspondente. Assim o remoto Git não anuncia uma versão
irrecuperável por falta dos objetos:

```bash
uv run dvc push -r dagshub
```

O `dvc push` cobre o workbook original da UCI, o CSV bruto, os datasets preparados, a referência,
o modelo e as figuras — o conjunto inteiro de objetos do DVC. Conferir o conjunto compartilhado,
não apenas o CSV e o modelo.

Em um checkout autorizado, recuperar os objetos necessários para o commit atual:

```bash
uv run dvc pull -r dagshub
```

O `dvc pull` traz também o workbook original da UCI, sem o qual o estágio `acquire` não roda.
O fluxo continua reproduzível localmente com `uv run dvc repro`; DagsHub fornece armazenamento e
visualização dos arquivos/pipelines DVC, não compute para treinar o modelo. A equipe deve
sincronizar os metadados Git correspondentes aos objetos DVC e evitar misturar ponteiros de um
commit com objetos de outra versão.

## Controles e verificação

- Só enviar dados públicos/aprovados para compartilhamento e compatíveis com os termos da fonte.
- Não adicionar datasets ou modelos binários diretamente ao Git; o Git recebe apenas os ponteiros
  gerados pelo DVC e metadados do pipeline.
- Manter separados dados de referência e dados de produção simulados também no versionamento.
- Não versionar tokens, `.dvc/config.local`, dados pessoais, segredos ou artefatos não aprovados.
- Antes da primeira sincronização, confirmar que o repositório DagsHub existe, o remote aponta para
  ele, os objetos DVC selecionados estão autorizados e o acesso funciona.
- Verificar configuração com `uv run dvc remote list`, integridade local com `uv run dvc status` e
  disponibilidade do cache remoto com `uv run dvc status -c -r dagshub`.
- Demonstrar recuperação em checkout e cache DVC separados, sem apagar o cache de trabalho;
  recuperar a mesma versão e conferir hashes. `dvc pull` em um cache já preenchido não comprova
  recuperação remota.
- Retenção abrange objetos remotos e caches locais: apagar ponteiros Git não remove o conteúdo
  armazenado; não executar coleta de lixo ou exclusão de versões como parte deste guia.

## Referências

- [DagsHub — integração DVC e Storage](https://dagshub.com/docs/integration_guide/dvc/)
- [DagsHub — conectar repositório existente](https://dagshub.com/docs/quick_start/connect_existing_project/)
- [DagsHub — versionar dados](https://dagshub.com/docs/quick_start/version_data/)
- [DVC — armazenamento S3 e servidores compatíveis](https://dvc.org/doc/user-guide/data-management/remote-storage/amazon-s3)

Documentação consultada em 2026-10-26. Valores de remote e credenciais são específicos da conta
e do repositório e devem ser copiados da interface do DagsHub.
