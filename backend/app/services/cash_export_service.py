"""Exports of the selected closing tab, preserving unknown amounts."""
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


PAYMENTS = [('nome','Forma de Pagamento'),('entradas','Entrada'),('saidas','Saída'),('total','Total'),('conferencia','Conferência'),('diferenca','Diferença')]
MOVEMENTS = [('data','Data'),('documento','Documento'),('descricao','Descrição'),('quantidade','Quantidade'),('valor','Valor'),('usuario','Usuário')]
ORDERS = [('pedido','Pedido'),('data','Emissão'),('cliente','Cliente'),('status','Status'),('valor','Valor'),('cancelamento','Cancelamento'),('motivo','Motivo')]
PRODUCTS = [('pedido','Pedido'),('sequencia','Item'),('produto','Produto'),('descricao','Descrição'),('quantidade','Quantidade'),('valor','Valor')]


def closing_table(detail, tab):
    if tab == 'financeiro':
        columns = [(c['key'],c['label']) for c in detail.get('cash_payment_columns',[])] or PAYMENTS
        return detail.get('cash_payments_available'), columns, detail.get('cash_payments',[])
    for category, field, columns in [('vendas','cash_orders',ORDERS),('produtos','cash_order_products',PRODUCTS),('canceladas','cash_cancellations',ORDERS)]:
        if tab == category and detail.get(field+'_available'):
            return True, columns, detail.get(field,[])
    return detail.get('cash_items_available'), MOVEMENTS, detail.get('cash_items',{}).get(tab,[])


def export_closing(detail, closing_id, tab, format):
    available, columns, records = closing_table(detail,tab)
    if not available:
        raise ValueError('Dados desta aba ainda não sincronizados.')
    if detail.get('cash_items_truncated'):
        raise ValueError('O fechamento excede o limite de exportação. Consulte o ERP para obter o histórico completo.')
    rows = [[label for _,label in columns]] + [[row.get(key) for key,_ in columns] for row in records]
    if tab == 'financeiro':
        totals = ['TOTAL GERAL']
        for key,_ in columns[1:]:
            values = [row.get(key) for row in records]
            totals.append(None if any(v is None for v in values) else sum((Decimal(str(v)) for v in values),Decimal(0)))
        rows.append(totals)
    stream = BytesIO()
    if format == 'excel':
        book=Workbook();sheet=book.active;sheet.title='Fechamento'
        sheet.append(['Fechamento de Caixa',str(closing_id),tab])
        for row in rows:
            sheet.append([("'"+value if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')) else value) for value in row])
        sheet.freeze_panes='A3';book.save(stream)
        return stream.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','xlsx'
    style=getSampleStyleSheet()
    document=SimpleDocTemplate(stream,pagesize=landscape(A4),leftMargin=24,rightMargin=24,topMargin=24,bottomMargin=24)
    formatted=[[Paragraph(escape('—' if value is None else str(value)),style['Normal']) for value in row] for row in rows]
    table=Table(formatted,colWidths=[document.width/len(columns)]*len(columns),repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eef2ff')),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#cbd5e1')),('VALIGN',(0,0),(-1,-1),'TOP')]))
    document.build([Paragraph('Fechamento de Caixa',style['Title']),Paragraph(escape(f'ID: {closing_id} | Aba: {tab}'),style['Normal']),Spacer(1,12),table])
    return stream.getvalue(),'application/pdf','pdf'
