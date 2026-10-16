class ReportPermissionError(PermissionError):
    pass


class ReportPermissionValidator:
    FINANCE_ROLES = {"administrator", "administrador", "admin", "erp-admin", "finance", "financeiro", "supervisor"}

    def validate(self, category: str, user: dict) -> None:
        if user.get('auth_source') == 'pigo':
            if category == 'finance' and 'finance.read' not in user.get('permissions', []):
                raise ReportPermissionError("O usuário não possui acesso às fontes financeiras.")
            return
        role = str(user.get("role") or user.get("perfil") or "").lower()
        if category == "finance" and role not in self.FINANCE_ROLES:
            raise ReportPermissionError("O usuário não possui acesso às fontes financeiras.")
