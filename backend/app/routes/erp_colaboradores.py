from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database.erp_connection import get_erp_db

router = APIRouter(prefix="/erp", tags=["ERP Colaboradores"])


@router.get("/colaboradores-completo")
def listar_colaboradores_completo(erp_db: Session = Depends(get_erp_db)):
    query = text("""
        SELECT
            c.COL_EMPRESA,
            c.COL_FUNCAO,
            c.COL_SALARIO,
            c.COL_STATUS,
            c.COL_PROFISSAO,
            c.COL_CPF,
            c.COL_RG,
            c.COL_ESTADO_CIVIL,
            c.COL_DT_CADASTRO,
            c.COL_EDITADO,
            c.COL_CARTEIRA_TRABALHO,
            c.COL_SERIE,
            c.COL_TITULO_ELEITOR,
            c.COL_TITULO_ZONA,
            c.COL_PIS,
            c.COL_DATA_ADMISSAO,
            c.COL_DATA_AFASTAMENTO,
            c.COL_HORARIO_ENTRADA,
            c.COL_INTERVALO_INCIAIL,
            c.COL_INTERVALO_FINAL,
            c.COL_HORARIO_SAIDA,
            c.COL_RAZAO_SOCIAL_REGISTRADA,
            c.COL_CARTAO_PONTO,
            c.COL_TITULO_SECAO,
            c.COL_SALARIO_VALOR,
            c.COL_PESSOA,

            p.PES_ID,
            p.PES_TIPO_PESSOA,
            p.PES_RSOCIAL_NOME,
            p.PES_FANTASIA_APELIDO,
            p.PES_CNPJ_CPF,
            p.PES_IE_RG,
            p.PES_ENDERECO,
            p.PES_COMPLEMENTO,
            p.PES_NUMERO,
            p.PES_BAIRRO,
            p.PES_CIDADE,
            p.PES_CEP,
            p.PES_TELEFONE,
            p.PES_FAX,
            p.PES_CELULAR,
            p.PES_EMAIL,
            p.PES_CONTATO,
            p.PES_OBSERVACAO,
            p.PES_DT_CADASTRO,
            p.PES_DT_NASCIMENTO,
            p.PES_STATUS,
            p.PES_CLIENTE,
            p.PES_FORNECEDOR,
            p.PES_VENDEDOR,
            p.PES_COLABORADOR,
            p.PES_TRANSPORTADOR,
            p.PES_SEXO,
            p.PES_PROFISSAO,
            p.PES_ULTIMA_ALTERACAO,
            p.PES_GUID
        FROM TB_COLABORADOR c
        JOIN TB_PESSOA p
          ON p.PES_ID = c.COL_PESSOA
        ROWS 100
    """)

    result = erp_db.execute(query)
    dados = []

    for row in result:
        dados.append({
            "colaborador": {
                "empresa": row[0],
                "funcao": row[1],
                "salario": row[2],
                "status": row[3],
                "profissao": row[4],
                "cpf_colaborador": row[5],
                "rg_colaborador": row[6],
                "estado_civil": row[7],
                "dt_cadastro_colaborador": str(row[8]) if row[8] else None,
                "editado": row[9],
                "carteira_trabalho": row[10],
                "serie": row[11],
                "titulo_eleitor": row[12],
                "titulo_zona": row[13],
                "pis": row[14],
                "data_admissao": str(row[15]) if row[15] else None,
                "data_afastamento": str(row[16]) if row[16] else None,
                "horario_entrada": str(row[17]) if row[17] else None,
                "intervalo_inicial": str(row[18]) if row[18] else None,
                "intervalo_final": str(row[19]) if row[19] else None,
                "horario_saida": str(row[20]) if row[20] else None,
                "razao_social_registrada": row[21],
                "cartao_ponto": row[22],
                "titulo_secao": row[23],
                "salario_valor": float(row[24]) if row[24] is not None else None,
                "pessoa_id": row[25]
            },
            "pessoa": {
                "pes_id": row[26],
                "tipo_pessoa": row[27],
                "nome": row[28],
                "fantasia_apelido": row[29],
                "cpf_cnpj": row[30],
                "ie_rg": row[31],
                "endereco": row[32],
                "complemento": row[33],
                "numero": row[34],
                "bairro": row[35],
                "cidade": row[36],
                "cep": row[37],
                "telefone": row[38],
                "fax": row[39],
                "celular": row[40],
                "email": row[41],
                "contato": row[42],
                "observacao": row[43],
                "dt_cadastro_pessoa": str(row[44]) if row[44] else None,
                "dt_nascimento": str(row[45]) if row[45] else None,
                "status_pessoa": row[46],
                "cliente": row[47],
                "fornecedor": row[48],
                "vendedor": row[49],
                "colaborador": row[50],
                "transportador": row[51],
                "sexo": row[52],
                "profissao_pessoa": row[53],
                "ultima_alteracao": str(row[54]) if row[54] else None,
                "guid": row[55]
            }
        })

    return dados