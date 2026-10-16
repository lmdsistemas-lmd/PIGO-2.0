from io import BytesIO
from typing import Dict, Any
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


class RelatorioPdfService:
    @staticmethod
    def gerar_pdf_bytes(relatorio: Dict[str, Any]) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(relatorio["nome"], styles["Title"]))
        elements.append(Spacer(1, 12))

        colunas = relatorio["colunas"]
        linhas = relatorio["linhas"]

        data = [colunas]
        for linha in linhas:
            data.append([str(linha.get(col, "")) for col in colunas])

        tabela = Table(data, repeatRows=1)
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        elements.append(tabela)
        doc.build(elements)

        buffer.seek(0)
        return buffer.read()