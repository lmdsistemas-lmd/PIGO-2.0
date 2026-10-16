"""Drop-in structure export, compatible with the agent supplied by the user.

Reads only Firebird system catalogs; no synchronization, activation or ERP writes.
"""
import json
from pathlib import Path
from datetime import datetime


def export_structure(connection, schema, target):
    data = {"generated_at": datetime.now().isoformat(), "tables": sorted(schema.tables),
            "columns": schema.columns, "primary_keys": schema.primary_keys, "foreign_keys": schema.foreign_keys}
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT TRIM(RDB$GENERATOR_NAME) FROM RDB$GENERATORS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY 1")
        data["generators"] = [row[0] for row in cursor.fetchall()]
        cursor.execute("""SELECT TRIM(P.RDB$PROCEDURE_NAME), TRIM(P.RDB$PARAMETER_NAME),
            P.RDB$PARAMETER_TYPE, P.RDB$PARAMETER_NUMBER FROM RDB$PROCEDURE_PARAMETERS P
            ORDER BY 1,3,4""")
        data["procedure_parameters"] = [{"procedure": row[0], "parameter": row[1], "direction": "input" if row[2] == 0 else "output", "position": row[3]} for row in cursor.fetchall()]
        cursor.execute("""SELECT TRIM(RDB$TRIGGER_NAME),TRIM(RDB$RELATION_NAME),RDB$TRIGGER_TYPE
            FROM RDB$TRIGGERS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY 1""")
        data["triggers"] = [{"name": row[0], "table": row[1], "type": row[2]} for row in cursor.fetchall()]
        cursor.execute("""SELECT TRIM(R.RDB$RELATION_NAME),TRIM(R.RDB$FIELD_NAME),F.RDB$FIELD_TYPE,
            F.RDB$FIELD_SUB_TYPE,F.RDB$FIELD_SCALE,F.RDB$FIELD_LENGTH,COALESCE(R.RDB$NULL_FLAG,F.RDB$NULL_FLAG,0)
            FROM RDB$RELATION_FIELDS R JOIN RDB$FIELDS F ON F.RDB$FIELD_NAME=R.RDB$FIELD_SOURCE
            JOIN RDB$RELATIONS T ON T.RDB$RELATION_NAME=R.RDB$RELATION_NAME
            WHERE COALESCE(T.RDB$SYSTEM_FLAG,0)=0 ORDER BY 1,R.RDB$FIELD_POSITION""")
        data["field_metadata"] = [{"table": row[0], "column": row[1], "type": row[2], "subtype": row[3], "scale": row[4], "length": row[5], "required": bool(row[6])} for row in cursor.fetchall()]
    finally:
        cursor.close()
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return str(target)


def main():
    import agent
    connection = None
    try:
        connection = agent.get_db_connection()
        schema = agent.FirebirdSchema(connection).load()
        target = export_structure(connection, schema, agent.DIAGNOSTIC_DIR / "schema_diagnostics.json")
        print(json.dumps({"success": True, "code": "SCHEMA_EXPORTED", "path": target,
                          "message": "Estrutura do ERP exportada sem registros comerciais."}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"success": False, "code": type(exc).__name__,
                          "message": "Não foi possível ler a estrutura do ERP. Verifique a conexão Firebird."}, ensure_ascii=False))
        return 1
    finally:
        if connection:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
