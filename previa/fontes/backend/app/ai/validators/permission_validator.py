class ReportPermissionError(PermissionError):
    pass


class ReportPermissionValidator:
    FINANCE_ROLES = {"administrator", "administrador", "admin", "erp-admin", "finance", "financeiro", "supervisor"}

    def validate(self, category: str, user: dict) -> None:
        role = str(user.get("role") or user.get("perfil") or "").lower()
        if category == "finance" and role not in self.FINANCE_ROLES:
            raise ReportPermissionError("O usuário não possui acesso às fontes financeiras.")
