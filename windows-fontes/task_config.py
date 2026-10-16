"""Prepare a native Windows Task Scheduler profile. No downloaded executable."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

from run_pigo import configured_environment


def prepare_task(app_root, python, output, name="PigoDashboardTest", port=4010):
    if not re.fullmatch(r"Pigo[A-Za-z0-9_-]{1,60}", name) or not 1 <= port <= 65535:
        raise ValueError("Nome de tarefa ou porta invalida.")
    backend, _ = configured_environment(app_root.resolve())
    if not python.is_file():
        raise ValueError("Python do backend nao encontrado.")
    output = output.resolve()
    if output.exists():
        raise ValueError("A pasta de saida deve ser nova; preserve a configuracao existente.")
    arguments = ["-u", str(output / "run_pigo.py"), "--app-root", str(backend.parent),
                 "--port", str(port), "--log-dir", str(output / "logs")]
    info = {"name": name, "task_path": "\\", "port": port, "app_root": str(backend.parent),
            "executable": str(python.resolve()), "arguments": subprocess.list2cmdline(arguments),
            "working_directory": str(backend), "log_directory": str(output / "logs"),
            "frontend_entry": "explicit-react-routes-v1", "scheduler": "Windows Task Scheduler"}
    output.mkdir(parents=True)
    (output / "logs").mkdir()
    scripts = Path(__file__).resolve().parent
    for filename in ["run_pigo.py", "frontend_shell.py", "Test-PigoInstance.ps1", "Manage-Task.ps1"]:
        shutil.copy2(scripts / filename, output / filename)
    (output / "task.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", default="PigoDashboardTest")
    parser.add_argument("--port", type=int, default=4010)
    args = parser.parse_args()
    try:
        prepare_task(args.app_root, args.python, args.output, args.name, args.port)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Arquivos preparados em {args.output}. Nenhuma tarefa registrada/iniciada.")


if __name__ == "__main__":
    main()
