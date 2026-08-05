from __future__ import annotations

import json
from pathlib import Path

from bookcorpusbuilder.outline_contract import contract_json_schema


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    target = project / "schemas" / "book_outline_contract_v1.schema.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(contract_json_schema(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(target)


if __name__ == "__main__":
    main()
