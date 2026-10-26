#!/usr/bin/env bash
# Configura o remote DagsHub do DVC a partir do arquivo .env local.
#
# O .env NUNCA é versionado (.gitignore) e os segredos ficam em
# .dvc/config.local, também ignorado. Este script apenas traduz as variáveis
# de ambiente em configuração do DVC; ele não imprime os valores.
#
# Uso:
#   scripts/configure_dagshub.sh [caminho_do_env]
#
# Depois de configurado:
#   uv run dvc remote list
#   uv run dvc push -r dagshub
#   uv run dvc pull -r dagshub   # em checkout/cache separado

set -euo pipefail

ENV_FILE="${1:-.env}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f "$ENV_FILE" ]; then
  echo "Arquivo $ENV_FILE nao encontrado. Copie .env.example para .env e preencha." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "./$ENV_FILE"
set +a

missing=()
for name in DAGSHUB_OWNER DAGSHUB_REPO DAGSHUB_ACCESS_KEY_ID DAGSHUB_SECRET_ACCESS_KEY; do
  if [ -z "${!name:-}" ]; then
    missing+=("$name")
  fi
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "Variaveis ausentes ou vazias em $ENV_FILE: ${missing[*]}" >&2
  exit 1
fi

if uv run dvc remote list | grep -q '^dagshub'; then
  uv run dvc remote modify dagshub url s3://dvc
else
  uv run dvc remote add dagshub s3://dvc
fi
uv run dvc remote modify dagshub endpointurl \
  "https://dagshub.com/${DAGSHUB_OWNER}/${DAGSHUB_REPO}.s3"
uv run dvc remote default dagshub

# Credenciais apenas na configuracao local; nunca no arquivo versionado.
uv run dvc remote modify dagshub --local access_key_id "${DAGSHUB_ACCESS_KEY_ID}"
uv run dvc remote modify dagshub --local secret_access_key "${DAGSHUB_SECRET_ACCESS_KEY}"

unset DAGSHUB_ACCESS_KEY_ID DAGSHUB_SECRET_ACCESS_KEY

echo "Remote dagshub configurado para ${DAGSHUB_OWNER}/${DAGSHUB_REPO}."
uv run dvc remote list
echo "Confira o acesso antes de sincronizar: uv run dvc status -c -r dagshub"
