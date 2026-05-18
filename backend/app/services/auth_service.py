from sqlalchemy import text
from sqlalchemy.orm import Session


def autenticar_usuario_erp(db: Session, login: str, senha: str):
    login_digitado = str(login or "").strip()
    senha_digitada = str(senha or "").strip()

    print("=" * 60)
    print("[AUTH] Tentativa de login")
    print(f"[AUTH] Login digitado: '{login_digitado}'")

    sql = text("""
        SELECT
            TRIM(u.usu_login) AS usu_login,
            TRIM(u.usu_nome) AS usu_nome,
            TRIM(u.usu_senha) AS usu_senha,
            TRIM(u.usu_administrador) AS usu_administrador
        FROM tb_usuario u
        WHERE UPPER(TRIM(u.usu_login)) = UPPER(:login)
    """)

    result = db.execute(sql, {"login": login_digitado}).mappings().first()

    if not result:
        print("[AUTH] Usuário não encontrado.")
        return None

    login_banco = str(result.get("usu_login") or "").strip()
    nome_usuario = str(result.get("usu_nome") or "").strip()
    senha_banco = str(result.get("usu_senha") or "").strip()
    administrador = str(result.get("usu_administrador") or "").strip()

    print(f"[AUTH] Usuário encontrado: {nome_usuario}")

    if administrador.upper() != "S":
        print("[AUTH] Usuário não é administrador.")
        return None

    # comparação ignorando capslock
    if senha_banco.upper() != senha_digitada.upper():
        print("[AUTH] Senha inválida.")
        return None

    print("[AUTH] Login autorizado.")

    return {
        "id": 1,
        "login": login_banco,
        "nome": nome_usuario,
        "perfil": "Administrador ERP",
    }