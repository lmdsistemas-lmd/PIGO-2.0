from io import BytesIO
import unittest
from openpyxl import load_workbook
from app.services.cash_export_service import export_closing

class CashExportTests(unittest.TestCase):
    def test_export_preserves_unknown_totals_and_escapes_spreadsheet_formulas(self):
        detail={'cash_payments_available':True,'cash_payments':[{'nome':'=HYPERLINK("invalid")','entradas':100,'saidas':0,'total':100,'conferencia':None,'diferenca':None}]}
        data,mime,ext=export_closing(detail,'1','financeiro','excel')
        self.assertEqual(ext,'xlsx');self.assertIn('spreadsheet',mime)
        rows=list(load_workbook(BytesIO(data),data_only=False).active.values)
        self.assertTrue(rows[2][0].startswith("'="))
        self.assertEqual(rows[-1][0],'TOTAL GERAL');self.assertEqual(rows[-1][1],100)
        self.assertIsNone(rows[-1][4]);self.assertIsNone(rows[-1][5])
        pdf,_,_=export_closing(detail,'<1>','financeiro','pdf');self.assertTrue(pdf.startswith(b'%PDF'))

    def test_unavailable_or_truncated_data_is_not_exported_as_complete(self):
        for detail in [{},{'cash_payments_available':True,'cash_items_truncated':True}]:
            with self.assertRaises(ValueError):export_closing(detail,'1','financeiro','excel')
