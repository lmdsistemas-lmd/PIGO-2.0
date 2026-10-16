from io import BytesIO
from typing import Dict, Any
from openpyxl import Workbook


class RelatorioExportService:
    @staticmethod
    def gerar_excel_bytes(relatorio: Dict[str, Any]) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "Relatorio"

        colunas = relatorio["colunas"]
        linhas = relatorio["linhas"]

        if colunas:
            ws.append(colunas)

        for linha in linhas:
            ws.append([linha.get(col) for col in colunas])

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.read()