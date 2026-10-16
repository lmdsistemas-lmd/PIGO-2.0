import ast
import json
import re
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND_DIR / "app"

ERP_COMPANY_FIELDS = re.compile(
    r"\b(empresa_id|emp_id|empresa|rec_empresa|cli_empresa|pev_empresa|pevi_empresa|"
    r"os_empresa|mov_empresa|pag_empresa|prd_empresa|prde_empresa|col_empresa|aud_empresa)\b",
    re.IGNORECASE,
)
SQL_MARKERS = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|JOIN|WHERE)\b", re.IGNORECASE)
MIRROR_TABLE = re.compile(r"\bTB_[A-Z0-9_]+\b", re.IGNORECASE)
JOIN_PATTERN = re.compile(r"\bJOIN\b", re.IGNORECASE)


def line_for_offset(source: str, offset: int) -> int:
    return source[:offset].count("\n") + 1


def function_for_line(tree: ast.AST, line: int) -> str | None:
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = getattr(node, "lineno", 0)
            end = getattr(node, "end_lineno", start)
            if start <= line <= end:
                if best is None or start >= best[0]:
                    best = (start, node.name)
    return best[1] if best else None


def string_literals(source: str):
    pattern = re.compile(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\n]*(?:\\.[^"\n]*)*"|\'[^\'\n]*(?:\\.[^\'\n]*)*\')')
    for match in pattern.finditer(source):
        raw = match.group(0)
        try:
            value = ast.literal_eval(raw)
        except Exception:
            continue
        if isinstance(value, str) and SQL_MARKERS.search(value):
            yield match.start(), value


def assess_sql(sql: str) -> tuple[str | None, str]:
    normalized = " ".join(sql.split())
    if "to_regclass" in normalized.lower():
        return None, ""

    has_mirror_table = bool(MIRROR_TABLE.search(normalized))
    has_company_field = bool(ERP_COMPANY_FIELDS.search(normalized))
    has_tenant = "tenant_id" in normalized.lower()
    has_join = bool(JOIN_PATTERN.search(normalized))

    if not has_mirror_table and not has_company_field:
        return None, ""

    if has_mirror_table and not has_tenant:
        if has_join:
            return "critico", "Consulta em tabela espelhada com JOIN sem tenant_id; adicionar tenant_id em WHERE e ON dos JOINs."
        return "alto", "Consulta em tabela espelhada sem filtro tenant_id; usar tenant autenticado."

    if has_company_field and not has_tenant:
        return "alto", "Consulta usa identificador de empresa original sem tenant_id; combinar tenant_id + empresa original."

    if has_join:
        joins = re.findall(r"\bJOIN\b", normalized, flags=re.IGNORECASE)
        tenant_refs = re.findall(r"tenant_id", normalized, flags=re.IGNORECASE)
        if len(tenant_refs) < len(joins) + 1:
            return "medio", "Validar se todos os JOINs entre tabelas espelhadas incluem alias.tenant_id = alias_raiz.tenant_id."

    return "baixo", "Consulta menciona tenant_id; revisar se tenant vem da sessao/JWT e nao do frontend."


def _is_runtime_guarded(path: Path, source: str) -> bool:
    relative = path.relative_to(BACKEND_DIR)
    if relative.parts[:2] == ("app", "repositories"):
        return True
    return "ERPQueryService" in source or "BaseRepository" in source


def audit_file(path: Path):
    source = path.read_text(encoding="utf-8", errors="ignore")
    runtime_guarded = _is_runtime_guarded(path, source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        tree = ast.Module(body=[], type_ignores=[])

    findings = []
    for offset, sql in string_literals(source):
        risk, suggestion = assess_sql(sql)
        if not risk:
            continue
        original_risk = risk
        if runtime_guarded and risk in {"critico", "alto"}:
            risk = "medio"
            suggestion = (
                "Consulta passa pela camada ERPQueryService/BaseRepository; "
                "tenant_id é injetado em runtime. Revisar manualmente subqueries/joins derivados."
            )
        line = line_for_offset(source, offset)
        findings.append(
            {
                "file": str(path.relative_to(BACKEND_DIR)),
                "function": function_for_line(tree, line),
                "line": line,
                "risk": risk,
                "original_risk": original_risk,
                "runtime_guarded": runtime_guarded,
                "query": " ".join(sql.split())[:500],
                "suggestion": suggestion,
            }
        )

    return findings


def main():
    findings = []
    for path in sorted(APP_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        findings.extend(audit_file(path))

    severity_order = {"critico": 0, "alto": 1, "medio": 2, "baixo": 3}
    findings.sort(key=lambda item: (severity_order.get(item["risk"], 9), item["file"], item["line"]))

    report = {
        "total_findings": len(findings),
        "by_risk": {
            risk: sum(1 for item in findings if item["risk"] == risk)
            for risk in ["critico", "alto", "medio", "baixo"]
        },
        "findings": findings,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if any(item["risk"] in {"critico", "alto"} for item in findings):
        sys.exit(2)


if __name__ == "__main__":
    main()
