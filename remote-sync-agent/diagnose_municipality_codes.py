"""Read-only diagnostic for the ERP municipality-code contract."""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from firebird_provider import create_provider


FIREBIRD_TYPE_NAMES = {
    7: "SMALLINT",
    8: "INTEGER",
    10: "FLOAT",
    12: "DATE",
    13: "TIME",
    14: "CHAR",
    16: "BIGINT/NUMERIC",
    27: "DOUBLE",
    35: "TIMESTAMP",
    37: "VARCHAR",
    261: "BLOB",
}


def normalize_ibge_code(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float):
        if not value.is_integer():
            return None
        raw = str(int(value))
    else:
        raw = str(value).strip()
    digits = "".join(character for character in raw if character.isdigit())
    return digits if len(digits) == 7 else None


def connect():
    load_dotenv(Path(__file__).with_name(".env"))
    settings = {
        "host": os.getenv("FB_HOST"),
        "port": int(os.getenv("FB_PORT", "3050")),
        "database": os.getenv("FB_DATABASE"),
        "user": os.getenv("FB_USER"),
        "password": os.getenv("FB_PASS"),
        "charset": os.getenv("FB_CHARSET", "UTF8"),
        "client_path": os.getenv("FB_CLIENT_PATH"),
    }
    return create_provider(
        os.getenv("FIREBIRD_DRIVER", "firebird-driver")
    ).connect(settings)


def main():
    connection = connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT f.RDB$FIELD_TYPE, f.RDB$FIELD_LENGTH,
               f.RDB$CHARACTER_LENGTH, f.RDB$FIELD_SCALE
        FROM RDB$RELATION_FIELDS rf
        JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE
        WHERE rf.RDB$RELATION_NAME = 'TB_CIDADE'
          AND rf.RDB$FIELD_NAME = 'CID_CODIGO_MUNICIPIO'
        """
    )
    field = cursor.fetchone()
    if not field:
        raise RuntimeError(
            "Campo TB_CIDADE.CID_CODIGO_MUNICIPIO não encontrado."
        )

    cursor.execute(
        """
        SELECT CID_ID, CID_NOME, CID_CODIGO_MUNICIPIO
        FROM TB_CIDADE
        WHERE CID_CODIGO_MUNICIPIO IS NOT NULL
        ROWS 10
        """
    )
    examples = [
        {
            "city_id": str(row[0]).strip(),
            "city": str(row[1] or "").strip(),
            "received_code": str(row[2]).strip(),
        }
        for row in cursor.fetchall()
    ]

    cursor.execute("SELECT CID_CODIGO_MUNICIPIO FROM TB_CIDADE")
    values = [row[0] for row in cursor.fetchall()]
    valid = [normalize_ibge_code(value) for value in values]
    null_or_blank = sum(
        value is None or not str(value).strip() for value in values
    )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM TB_CLIENTE C
        JOIN TB_PESSOA P ON P.PES_ID = C.CLI_PESSOA
        LEFT JOIN TB_CIDADE CID ON CID.CID_ID = P.PES_CIDADE
        """
    )
    linked_clients = int(cursor.fetchone()[0])
    connection.close()

    print(
        json.dumps(
            {
                "relationship": (
                    "TB_CLIENTE.CLI_PESSOA -> TB_PESSOA.PES_ID; "
                    "TB_PESSOA.PES_CIDADE -> TB_CIDADE.CID_ID; "
                    "TB_CIDADE.CID_CODIGO_MUNICIPIO"
                ),
                "field": {
                    "name": "TB_CIDADE.CID_CODIGO_MUNICIPIO",
                    "type": FIREBIRD_TYPE_NAMES.get(field[0], str(field[0])),
                    "byte_length": field[1],
                    "character_length": field[2],
                    "scale": field[3],
                },
                "examples": examples,
                "counts": {
                    "total_cities": len(values),
                    "valid": sum(code is not None for code in valid),
                    "invalid": len(values)
                    - sum(code is not None for code in valid)
                    - null_or_blank,
                    "null_or_blank": null_or_blank,
                    "distinct_valid": len({code for code in valid if code}),
                    "linked_clients": linked_clients,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
