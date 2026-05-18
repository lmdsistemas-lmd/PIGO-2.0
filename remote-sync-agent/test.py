import fdb
fdb.load_api(r'C:\Program Files (x86)\Firebird\Firebird_5_0\fbclient.dll')
conn = fdb.connect(dsn='127.0.0.1:3053/C:\\DATAGOO CLIENTES\\Clientes Firebird 5\\Dados\\rrimperio\\DADOS.FDB', user='SYSDBA', password='masterkey')
cur = conn.cursor()
cur.execute("SELECT TRIM(RDB$FIELD_NAME) FROM RDB$RELATION_FIELDS WHERE TRIM(RDB$RELATION_NAME) = 'TB_PEDIDO_VENDA_ITEM'")
print([r[0] for r in cur.fetchall()])
