"""CLI for validating a batch against the data contract.

Exit codes:

- ``0``: the batch satisfies the contract;
- ``2``: the batch was rejected; the diagnostic lists rule, column and count, never
  client records;
- ``1``: the batch could not be read or the contract could not be applied.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from credit_monitoring.config import load_config
from credit_monitoring.contracts import CONTRACT_VERSION, ContractViolation, validate_batch

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONTRACT_VIOLATION = 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Valida um lote contra o contrato de dados (Pandera)."
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--input", required=True, help="CSV a validar")
    parser.add_argument(
        "--inference",
        action="store_true",
        help="Valida como lote de inferencia (sem alvo obrigatorio)",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    try:
        frame = pd.read_csv(args.input)
    except (OSError, ValueError) as error:
        print(f"Erro ao ler o lote: {error}", file=sys.stderr)
        return EXIT_ERROR

    try:
        validate_batch(frame, config, labeled=not args.inference)
    except ContractViolation as violation:
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "contract_version": CONTRACT_VERSION,
                    **violation.to_dict(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return EXIT_CONTRACT_VIOLATION

    print(
        json.dumps(
            {
                "status": "accepted",
                "contract_version": CONTRACT_VERSION,
                "rows": len(frame),
                "input": str(Path(args.input)),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
