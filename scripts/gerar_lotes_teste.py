"""Gera os lotes de inferencia do laboratorio de modelos (recorte 1.6-O6).

Escreve em ``data/test/``. Fontes e restricoes:

- as linhas vem **apenas** da particao de treino (21.000 linhas): a validacao e
  o teste nunca sao lidos;
- os IDs sao novos e sequenciais (900001+): nenhum cliente real e reproduzido;
- as features monetarias recebem um jitter multiplicativo deterministico de
  +-2%, o que preserva o perfil de risco e a ordem de grandeza, mas impede
  que qualquer linha do lote seja copia identica de uma linha de origem;
- as colunas status (PAY_*) e de governanca sao mantidas: sao codigos
  documentados e o contrato nao os restringe;
- a coluna de alvo e removida: o laboratorio e uma tela de inferencia.

Os arquivos ficam em ``tmp/``, que esta no ``.gitignore``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

from credit_monitoring.config import feature_columns, load_config

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "test"
TRAIN = REPO / "data" / "processed" / "train.csv"
SEED = 42
JITTER = 0.02
N_ROWS = 200
ID_BASE = 900_001

CONFIG = load_config()
DATASET = CONFIG["dataset"]
CANONICAL = [DATASET["id_column"], *feature_columns(CONFIG), *DATASET["governance_features"]]
TARGET = DATASET["canonical_target"]
MONEY = [c for c in feature_columns(CONFIG) if c.startswith(("BILL_AMT", "PAY_AMT"))] + [
    "LIMIT_BAL"
]


def profiles() -> list[tuple[str, dict[str, float]]]:
    """Seis perfis construidos a mao, todos dentro da faixa empirica observada."""
    zero_pays = {f"PAY_{i}": 0.0 for i in (0, 2, 3, 4, 5, 6)}
    zero_bills = {f"BILL_AMT{i}": 0.0 for i in range(1, 7)}
    zero_payments = {f"PAY_AMT{i}": 0.0 for i in range(1, 7)}
    return [
        (
            "pagador_exemplar",
            {
                "LIMIT_BAL": 200_000,
                **zero_pays,
                **zero_bills,
                **{f"PAY_AMT{i}": 30_000.0 for i in range(1, 7)},
                "AGE": 45.0,
            },
        ),
        (
            "uso_intenso_sem_atraso",
            {
                "LIMIT_BAL": 500_000,
                **zero_pays,
                **{f"BILL_AMT{i}": 120_000.0 for i in range(1, 7)},
                **{f"PAY_AMT{i}": 120_000.0 for i in range(1, 7)},
                "AGE": 38.0,
            },
        ),
        (
            "fatura_alta_limite_curto",
            {
                "LIMIT_BAL": 30_000,
                "PAY_0": 1.0,
                **{f"PAY_{i}": 0.0 for i in (2, 3, 4, 5, 6)},
                **{f"BILL_AMT{i}": 250_000.0 for i in range(1, 7)},
                **{f"PAY_AMT{i}": 5_000.0 for i in range(1, 7)},
                "AGE": 41.0,
            },
        ),
        (
            "atraso_longo",
            {
                "LIMIT_BAL": 50_000,
                "PAY_0": 8.0,
                "PAY_2": 7.0,
                "PAY_3": 6.0,
                "PAY_4": 5.0,
                "PAY_5": 4.0,
                "PAY_6": 3.0,
                **{f"BILL_AMT{i}": 150_000.0 for i in range(1, 7)},
                **zero_payments,
                "AGE": 33.0,
            },
        ),
        (
            "adimplente_tipico",
            {
                "LIMIT_BAL": 20_000,
                "PAY_0": 2.0,
                "PAY_2": 2.0,
                "PAY_3": 1.0,
                "PAY_4": 1.0,
                "PAY_5": 1.0,
                "PAY_6": 0.0,
                **{f"BILL_AMT{i}": 80_000.0 for i in range(1, 7)},
                **{f"PAY_AMT{i}": 1_000.0 for i in range(1, 7)},
                "AGE": 25.0,
            },
        ),
        (
            "credito_na_fatura",
            {
                "LIMIT_BAL": 100_000,
                **zero_pays,
                "BILL_AMT1": -5_000.0,
                "BILL_AMT2": 10_000.0,
                **{f"BILL_AMT{i}": 10_000.0 for i in range(3, 7)},
                **{f"PAY_AMT{i}": 1_000.0 for i in range(1, 7)},
                "AGE": 29.0,
            },
        ),
    ]


def row_from_profile(profile: dict[str, float]) -> dict[str, float]:
    row = {column: 0.0 for column in CANONICAL}
    row.update(profile)
    row["SEX"] = 1.0
    row["EDUCATION"] = 2.0
    row["MARRIAGE"] = 1.0
    return row


def jitter(frame: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Jitter multiplicativo deterministico nas colunas monetarias."""
    out = frame.copy()
    for column in MONEY:
        values = out[column].to_numpy(dtype=float)
        factor = rng.uniform(1 - JITTER, 1 + JITTER, size=values.shape)
        jittered = np.where(values > 0, values * factor, values)
        out[column] = np.round(jittered, 2)
    return out


def sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    rng = np.random.default_rng(SEED)
    if not TRAIN.is_file():
        raise SystemExit(
            f"{TRAIN} nao existe: e a saida do estagio DVC 'prepare'. "
            "Rode 'uv run dvc repro prepare' (ou 'uv run dvc pull -r dagshub') antes."
        )
    train = pd.read_csv(TRAIN)
    if TARGET not in train.columns or len(train) != 21_000:
        raise SystemExit(f"{TRAIN} inesperado: esperado o treino de 21.000 linhas com o alvo.")

    sampled = jitter(train.sample(n=N_ROWS - 6, random_state=SEED), rng)
    sampled = sampled.reset_index(drop=True)
    sampled[CANONICAL] = sampled[CANONICAL].astype(float)

    hand = pd.DataFrame([row_from_profile(values) for _name, values in profiles()])
    hand = hand[CANONICAL].astype(float)

    batch = pd.concat([hand, sampled[CANONICAL]], ignore_index=True)
    batch[DATASET["id_column"]] = np.arange(ID_BASE, ID_BASE + len(batch))
    batch = batch[CANONICAL]

    targets = pd.concat(
        [
            pd.DataFrame({TARGET: [0.0] * 6}),
            train.sample(n=N_ROWS - 6, random_state=SEED).reset_index(drop=True)[[TARGET]],
        ],
        ignore_index=True,
    )

    batch.to_csv(OUT / "lote_teste_200.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    batch.assign(**{TARGET: targets[TARGET].to_numpy()}).to_csv(
        OUT / "lote_com_alvo.csv", index=False
    )

    hand_with_label = hand.copy()
    hand_with_label.insert(0, "perfil", [name for name, _ in profiles()])
    hand_with_label[DATASET["id_column"]] = np.arange(ID_BASE, ID_BASE + 6)
    hand_with_label.to_csv(OUT / "lote_perfis_6.csv", index=False)

    smoke = pd.DataFrame(
        [
            row_from_profile(
                {
                    "LIMIT_BAL": 50_000,
                    "PAY_0": 0.0,
                    "BILL_AMT1": 20_000,
                    "PAY_AMT1": 20_000,
                    "AGE": 30.0,
                }
            ),
            row_from_profile(
                {
                    "LIMIT_BAL": 30_000,
                    "PAY_0": 2.0,
                    "BILL_AMT1": 45_000,
                    "PAY_AMT1": 1_000,
                    "AGE": 52.0,
                }
            ),
            row_from_profile(
                {
                    "LIMIT_BAL": 20_000,
                    "PAY_0": 3.0,
                    "BILL_AMT1": 60_000,
                    "PAY_AMT1": 0.0,
                    "AGE": 27.0,
                }
            ),
        ]
    )[CANONICAL].astype(float)
    smoke[DATASET["id_column"]] = np.arange(800_001, 800_001 + len(smoke))
    smoke.to_csv(OUT / "exemplo_lote_inferencia.csv", index=False)

    invalid = batch.head(4).copy()
    invalid.loc[1, DATASET["id_column"]] = invalid.loc[0, DATASET["id_column"]]
    invalid.loc[2, "LIMIT_BAL"] = 0.0
    invalid.loc[3, "AGE"] = 17.0
    invalid.loc[0, "PAY_AMT1"] = np.nan
    invalid.to_csv(OUT / "lote_rejeitado.csv", index=False)

    manifest = {
        "generator": "scripts/gerar_lotes_teste.py",
        "seed": SEED,
        "jitter": JITTER,
        "source": {
            "path": "data/processed/train.csv",
            "sha256": sha256(TRAIN),
            "rows": int(len(train)),
            "note": "Somente a particao de treino; validacao e teste nunca sao lidos.",
        },
        "files": {},
    }
    for path in sorted(OUT.glob("*.csv")):
        frame = pd.read_csv(path)
        manifest["files"][path.name] = {
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
            "sha256": sha256(path),
        }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print("gerados em", OUT)
    for path in sorted(OUT.glob("*.csv")):
        frame = pd.read_csv(path)
        print(f"  {path.name}: {len(frame)} linhas, {len(frame.columns)} colunas")


if __name__ == "__main__":
    main()
