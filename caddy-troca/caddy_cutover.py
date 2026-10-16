"""Prepare/apply one PIGO upstream change, with private backups and ETag checks."""
import argparse
import copy
import ctypes
import hashlib
import html
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler, Request

HOST = "pigo.lmdsistemasdev.qzz.io"
NEW_DIAL = "127.0.0.1:4010"
OLD_DIALS = {"127.0.0.1:4000", "127.0.0.1:5176"}


class CutoverError(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def changed_config(original):
    result = copy.deepcopy(original)
    matches, changed = [], []

    def visit(node, inside=False, path=()):
        if isinstance(node, list):
            for i, value in enumerate(node):
                visit(value, inside, path + (i,))
        elif isinstance(node, dict):
            hosts = [host for matcher in node.get("match", []) for host in matcher.get("host", [])]
            if hosts:
                if HOST not in hosts:
                    return
                if hosts != [HOST]:
                    raise CutoverError("O grupo PIGO compartilha outros hosts; nenhuma alteracao automatica.")
                matches.append(path)
                inside = True
            if inside and node.get("handler") == "reverse_proxy":
                for i, upstream in enumerate(node.get("upstreams", [])):
                    if upstream.get("dial") not in OLD_DIALS:
                        raise CutoverError("Destino PIGO diferente do diagnostico; nenhuma alteracao.")
                    changed.append((path + ("upstreams", i, "dial"), upstream["dial"]))
                    upstream["dial"] = NEW_DIAL
            for key, value in node.items():
                visit(value, inside, path + (key,))

    visit(result.get("apps", {}).get("http", {}), path=("apps", "http"))
    if len(matches) != 1 or len(changed) != 2 or {old for _, old in changed} != OLD_DIALS:
        raise CutoverError("Esperados um grupo exclusivo PIGO e exatamente os dois destinos4000/5176.")
    return result, changed


def caddy_tokens(text):
    # Caddy placeholders remain whole bare tokens. Comments and quoted/raw
    # strings are skipped structurally; heredocs require manual review.
    pattern = re.compile(r'\s+|\#[^\r\n]*|"(?:\\.|[^"\\])*"|`[^`]*`|[^\s"`#]+', re.DOTALL)
    tokens = []
    end = 0
    for match in pattern.finditer(text):
        if match.start() != end:
            raise CutoverError("Sintaxe Caddyfile nao reconhecida; revisar sem alterar.")
        end = match.end()
        token = match.group()
        if token.isspace() or token.startswith("#"):
            continue
        if "<<" in token:
            raise CutoverError("Caddyfile com heredoc exige revisao manual.")
        tokens.append((token, match.start(), match.end()))
    if end != len(text):
        raise CutoverError("Aspas ou tokens incompletos no Caddyfile.")
    return tokens


def patch_caddyfile(data):
    text = data.decode("utf-8-sig")
    tokens = caddy_tokens(text)
    depth, header, selected, body_start = 0, [], [], None

    def address_host(token):
        value = urlsplit(token if "://" in token else "//" + token)
        if value.username or value.password or value.path or value.query or value.fragment:
            return None
        return value.hostname

    for i, (token, start, end) in enumerate(tokens):
        if token == "{":
            if depth == 0:
                addresses = [part for item in header for part in item.rstrip(",").split(",") if part]
                hosts = [address_host(item) for item in addresses]
                body_start = i + 1 if HOST in hosts else None
                if body_start is not None and hosts != [HOST]:
                    raise CutoverError("Bloco do Caddyfile compartilha outros hosts.")
                header = []
            depth += 1
        elif token == "}":
            depth -= 1
            if depth < 0:
                raise CutoverError("Chaves desbalanceadas no Caddyfile.")
            if depth == 0 and body_start is not None:
                selected.append(tokens[body_start:i])
                body_start = None
        elif depth == 0:
            header.append(token)
    if depth or len(selected) != 1:
        raise CutoverError("Nao foi encontrado um unico bloco literal exclusivo do PIGO.")
    replacements = [(start, end, token) for token, start, end in selected[0] if token in OLD_DIALS]
    if len(replacements) != 2 or {token for _, _, token in replacements} != OLD_DIALS:
        raise CutoverError("Os destinos devem estar literais no bloco PIGO; imports ou outra estrutura exigem revisao.")
    for start, end, _ in reversed(replacements):
        text = text[:start] + NEW_DIAL + text[end:]
    return (b"\xef\xbb\xbf" if data.startswith(b"\xef\xbb\xbf") else b"") + text.encode("utf-8")


class Admin:
    def __init__(self, url="http://127.0.0.1:2019/config/"):
        self.url = url
        self.opener = build_opener(ProxyHandler({}))

    def read(self):
        with self.opener.open(self.url, timeout=15) as response:
            value = json.load(response)
            etag = response.headers.get("ETag", "")
        if not re.fullmatch(r'"/config/? [0-9a-fA-F]+"', etag):
            raise CutoverError("A API Caddy nao forneceu ETag reconhecida; nenhuma recarga sera feita.")
        return value, etag

    def replace(self, value, etag):
        request = Request(self.url, data=canonical(value).encode(), method="POST",
                          headers={"Content-Type": "application/json", "If-Match": etag})
        try:
            with self.opener.open(request, timeout=30) as response:
                response.read()
        except HTTPError as error:
            raise CutoverError(f"Recarga recusada pela API Caddy: HTTP{error.code}. Nenhum corpo de erro foi impresso.") from None


def adapt(executable, config, directory, diagnostics):
    result = subprocess.run([str(executable), "adapt", "--config", str(config), "--adapter", "caddyfile"],
                            cwd=directory, capture_output=True)
    if result.stderr:
        diagnostics.write_bytes(result.stderr)
    if result.returncode:
        raise CutoverError("Caddy nao adaptou o arquivo; diagnostico preservado somente na pasta privada.")
    return json.loads(result.stdout)


def secure_temp(directory):
    descriptor, name = tempfile.mkstemp(prefix=".pigo-", suffix=".tmp", dir=directory)
    if os.name == "nt":
        result = subprocess.run(["icacls.exe", name, "/inheritance:r", "/grant:r",
                                 "*S-1-5-18:F", "*S-1-5-32-544:F"], capture_output=True)
        if result.returncode:
            os.close(descriptor)
            Path(name).unlink(missing_ok=True)
            raise CutoverError("Nao foi possivel proteger o arquivo temporario; nenhuma configuracao escrita.")
    return descriptor, Path(name)


def adapt_candidate(executable, data, directory, diagnostics):
    # Caddy resolves imports relative to the source filename. Keep the temporary
    # source beside the real Caddyfile, with a private ACL before writing bytes.
    descriptor, temp = secure_temp(directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        return adapt(executable, temp, directory, diagnostics)
    finally:
        temp.unlink(missing_ok=True)


def replace_file(path, data):
    # ReplaceFileW preserves the original Windows file's ACL/metadata. Do not
    # ignore ACL merge errors or fall back to a less restrictive replacement.
    descriptor, temp = secure_temp(path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "nt":
            function = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
            function.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
            function.restype = ctypes.c_int
            if not function(str(path), str(temp), None, 0, None, None):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            temp.chmod(stat.S_IMODE(path.stat().st_mode))
            os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def prepare(config, executable, output, index, expected_hash, admin=None):
    admin = admin or Admin()
    original = config.read_bytes()
    if digest(original).lower() != expected_hash.lower():
        raise CutoverError("O hash do Caddyfile mudou desde o diagnostico; nenhuma alteracao.")
    if output.exists() and any(output.iterdir()):
        raise CutoverError("A pasta privada ja contem arquivos; preserve a preparacao existente.")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    live, _ = admin.read()
    adapted = adapt(executable, config, config.parent, output / "adapt-original.log")
    if canonical(adapted) != canonical(live):
        raise CutoverError("O Caddyfile nao equivale a configuracao ativa; revisar antes da troca.")
    candidate, changes = changed_config(live)
    patched = patch_caddyfile(original)
    candidate_file = output / "Caddyfile.candidate"
    candidate_file.write_bytes(patched)
    if canonical(adapt_candidate(executable, patched, config.parent, output / "adapt-candidate.log")) != canonical(candidate):
        raise CutoverError("A candidata alteraria mais campos que os destinos do PIGO; nenhuma alteracao aplicada.")
    (output / "Caddyfile.before").write_bytes(original)
    (output / "active-before.json").write_text(canonical(live), encoding="utf-8")
    (output / "active-after.json").write_text(canonical(candidate), encoding="utf-8")
    plan = {"config": str(config), "executable": str(executable), "index": str(index),
            "original_sha256": digest(original), "candidate_sha256": digest(patched),
            "index_sha256": digest(index.read_bytes()), "changed_upstreams": len(changes), "host": HOST,
            "before_json_sha256": digest(canonical(live).encode()), "after_json_sha256": digest(canonical(candidate).encode())}
    (output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return {"estado": "preparado, ainda nao aplicado", "dominio": HOST, "destinos_alterados": len(changes),
            "antes": sorted(OLD_DIALS), "depois": NEW_DIAL, "demais_campos_preservados": True, "pasta_privada": str(output)}


def load_plan(output):
    plan = json.loads((output / "plan.json").read_text())
    before = json.loads((output / "active-before.json").read_text())
    after = json.loads((output / "active-after.json").read_text())
    expected, _ = changed_config(before)
    if (plan["host"] != HOST or canonical(expected) != canonical(after)
            or digest(canonical(before).encode()) != plan["before_json_sha256"]
            or digest(canonical(after).encode()) != plan["after_json_sha256"]
            or digest((output / "Caddyfile.before").read_bytes()) != plan["original_sha256"]
            or digest((output / "Caddyfile.candidate").read_bytes()) != plan["candidate_sha256"]):
        raise CutoverError("Preparacao local modificada ou inconsistente; nenhuma alteracao.")
    return plan, before, after


def verify_public(index):
    markers = set(html.unescape(item) for item in re.findall(r'["\'](/assets/[^"\']+)["\']', index.read_text(encoding="utf-8")))
    if not markers:
        raise CutoverError("Build sem marcadores assets; revisar verificacao HTTPS antes de aplicar.")
    opener = build_opener(ProxyHandler({}))  # default TLS/hostname verification retained
    for route in ["/login", "/dashboard/vendas"]:
        request = Request("https://" + HOST + route, headers={"Accept": "text/html", "Accept-Encoding": "identity", "Cache-Control": "no-cache"})
        with opener.open(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            if response.status != 200 or not all(marker in body for marker in markers):
                raise CutoverError("HTTPS publico nao entregou o painel compilado esperado.")
    for marker in sorted(markers):
        request = Request("https://" + HOST + marker, headers={"Accept-Encoding": "identity"})
        with opener.open(request, timeout=10) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            extension = urlsplit(marker).path.rsplit(".", 1)[-1]
            if (response.status != 200 or "text/html" in content_type or not response.read(4096)
                    or (extension in {"js", "mjs"} and "javascript" not in content_type)
                    or (extension == "css" and "text/css" not in content_type)):
                raise CutoverError("HTTPS publico nao entregou os arquivos JS/CSS do build corretamente.")
    with opener.open("https://" + HOST + "/api/health", timeout=10) as response:
        body = json.load(response)
        if body.get("status") != "ok" or body.get("service") != "pigo":
            raise CutoverError("Saude da API publica nao confirmada.")
    try:
        opener.open("https://" + HOST + "/api/me/tenant", timeout=10).close()
    except HTTPError as error:
        if error.code == 401:
            return
    raise CutoverError("A consulta publica sem token nao retornou401.")


def rollback(output, admin=None):
    admin = admin or Admin()
    plan, before, after = load_plan(output)
    config = Path(plan["config"])
    live, etag = admin.read()
    if canonical(live) not in {canonical(before), canonical(after)}:
        raise CutoverError("Configuracao ativa mudou fora desta troca; retorno automatico bloqueado para preservar essas alteracoes.")
    if digest(config.read_bytes()) not in {plan["original_sha256"], plan["candidate_sha256"]}:
        raise CutoverError("Caddyfile mudou fora desta troca; retorno bloqueado para preservar essas alteracoes.")
    if canonical(live) == canonical(after):
        admin.replace(before, etag)
    replace_file(config, (output / "Caddyfile.before").read_bytes())
    return {"estado": "configuracao anterior restaurada", "dominio": HOST}


def apply(output, admin=None, verifier=verify_public):
    admin = admin or Admin()
    plan, before, after = load_plan(output)
    config, index = Path(plan["config"]), Path(plan["index"])
    live, etag = admin.read()
    if canonical(live) == canonical(after) and digest(config.read_bytes()) == plan["candidate_sha256"]:
        return {"estado": "troca ja aplicada", "dominio": HOST}
    if canonical(live) != canonical(before) or digest(config.read_bytes()) != plan["original_sha256"]:
        raise CutoverError("Configuracao ativa ou arquivo mudou desde a preparacao; nenhuma alteracao.")
    if digest(index.read_bytes()) != plan["index_sha256"]:
        raise CutoverError("Build alterado desde a preparacao; nenhuma alteracao.")
    replace_file(config, (output / "Caddyfile.candidate").read_bytes())
    try:
        admin.replace(after, etag)
        current, _ = admin.read()
        if canonical(current) != canonical(after):
            raise CutoverError("Nao foi confirmada a configuracao recarregada.")
        verifier(index)
    except Exception:
        try:
            rollback(output, admin)
        except Exception:
            # Restore only our own file write, even when a concurrent admin
            # update prevents restoring the in-memory configuration safely.
            if digest(config.read_bytes()) == plan["candidate_sha256"]:
                replace_file(config, (output / "Caddyfile.before").read_bytes())
            raise CutoverError("Falha na troca/verificacao e retorno automatico incompleto. Preserve a pasta privada e informe este resumo; nao encerre Caddy ou processos anteriores.") from None
        raise CutoverError("Troca/verificacao nao concluiu; configuracao anterior restaurada automaticamente.") from None
    return {"estado": "aplicado e verificado por HTTPS", "dominio": HOST, "destino": NEW_DIAL, "demais_campos_preservados": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "apply", "rollback"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--caddy", type=Path)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--expected-hash")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            if not all([args.config, args.caddy, args.index, args.expected_hash]):
                raise CutoverError("Informe os caminhos e o hash de origem para preparar.")
            result = prepare(args.config.resolve(), args.caddy.resolve(), args.output.resolve(), args.index.resolve(), args.expected_hash)
        elif args.action == "apply":
            result = apply(args.output.resolve())
        else:
            result = rollback(args.output.resolve())
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except CutoverError as error:
        print(str(error))
    except Exception as error:
        print("Operacao nao concluida: " + type(error).__name__ + ". Nenhum detalhe de configuracao foi impresso.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
