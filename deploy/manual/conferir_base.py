"""Compare an installed backend with the declared GitHub base, without importing it.

Uses only the standard library. Does not read .env, connect to a database,
start/stop processes, change files or call application endpoints.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(current_root, release_root):
    baseline = json.loads((release_root / "base_github.json").read_text(encoding="utf-8"))
    files = baseline["files"]
    matches = 0
    changed, missing = [], []
    for relative, expected in files.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or not relative.startswith("backend/"):
            raise ValueError("Caminho inesperado no manifesto da base")
        source = current_root / path
        if not source.is_file():
            missing.append(relative)
        elif sha256(source) != expected:
            changed.append(relative)
        else:
            matches += 1
    # Extra Python routes/services can contain licensing changes absent from GitHub.
    extra = sorted(str(path.relative_to(current_root)).replace(os.sep, "/")
                   for path in (current_root / "backend" / "app").rglob("*.py")
                   if "__pycache__" not in path.parts
                   and str(path.relative_to(current_root)).replace(os.sep, "/") not in files)
    installed = (current_root / "backend" / "app" / "main.py").is_file()
    return {
        "computador": os.environ.get("COMPUTERNAME", "não informado"),
        "python_bits": 64 if sys.maxsize > 2**32 else 32,
        "repositorio_base": baseline["repository"],
        "branch_base": baseline["branch"],
        "commit_base": baseline["commit"],
        "backend_encontrado": installed,
        "arquivos_iguais": matches,
        "arquivos_alterados": changed,
        "arquivos_ausentes": missing,
        "arquivos_python_adicionais": extra,
        "configuracao_env_existe": (current_root / "backend" / ".env").is_file(),
        "resultado": "BASE_CONFERE" if installed and not changed and not missing and not extra else "REVISAR_DIFERENCAS",
        "observacao": "Conferência somente de arquivos. Banco, migrações, licença, agente e instalação não foram executados.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--release-root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    if not args.current_root.is_dir():
        parser.error("A pasta do PIGO atual não existe neste computador.")
    result = check(args.current_root, args.release_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["resultado"] == "BASE_CONFERE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
