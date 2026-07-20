from fastapi import APIRouter, Depends

from app.routes.auth import get_current_user
from app.services.erp_query_service import ERPQueryService

router = APIRouter(prefix="/erp", tags=["ERP Colaboradores"])


@router.get("/colaboradores-completo")
def listar_colaboradores_completo(current_user: dict = Depends(get_current_user)):
    rows = ERPQueryService().fetch_all(
        """
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
        """
    )

    dados = []
    for row in rows:
        dados.append(
            {
                "colaborador": {
                    "empresa": row.get("COL_EMPRESA"),
                    "funcao": row.get("COL_FUNCAO"),
                    "salario": row.get("COL_SALARIO"),
                    "status": row.get("COL_STATUS"),
                    "profissao": row.get("COL_PROFISSAO"),
                    "cpf_colaborador": row.get("COL_CPF"),
                    "rg_colaborador": row.get("COL_RG"),
                    "estado_civil": row.get("COL_ESTADO_CIVIL"),
                    "dt_cadastro_colaborador": str(row.get("COL_DT_CADASTRO")) if row.get("COL_DT_CADASTRO") else None,
                    "editado": row.get("COL_EDITADO"),
                    "carteira_trabalho": row.get("COL_CARTEIRA_TRABALHO"),
                    "serie": row.get("COL_SERIE"),
                    "titulo_eleitor": row.get("COL_TITULO_ELEITOR"),
                    "titulo_zona": row.get("COL_TITULO_ZONA"),
                    "pis": row.get("COL_PIS"),
                    "data_admissao": str(row.get("COL_DATA_ADMISSAO")) if row.get("COL_DATA_ADMISSAO") else None,
                    "data_afastamento": str(row.get("COL_DATA_AFASTAMENTO")) if row.get("COL_DATA_AFASTAMENTO") else None,
                    "horario_entrada": str(row.get("COL_HORARIO_ENTRADA")) if row.get("COL_HORARIO_ENTRADA") else None,
                    "intervalo_inicial": str(row.get("COL_INTERVALO_INCIAIL")) if row.get("COL_INTERVALO_INCIAIL") else None,
                    "intervalo_final": str(row.get("COL_INTERVALO_FINAL")) if row.get("COL_INTERVALO_FINAL") else None,
                    "horario_saida": str(row.get("COL_HORARIO_SAIDA")) if row.get("COL_HORARIO_SAIDA") else None,
                    "razao_social_registrada": row.get("COL_RAZAO_SOCIAL_REGISTRADA"),
                    "cartao_ponto": row.get("COL_CARTAO_PONTO"),
                    "titulo_secao": row.get("COL_TITULO_SECAO"),
                    "salario_valor": float(row["COL_SALARIO_VALOR"]) if row.get("COL_SALARIO_VALOR") is not None else None,
                    "pessoa_id": row.get("COL_PESSOA"),
                },
                "pessoa": {
                    "pes_id": row.get("PES_ID"),
                    "tipo_pessoa": row.get("PES_TIPO_PESSOA"),
                    "nome": row.get("PES_RSOCIAL_NOME"),
                    "fantasia_apelido": row.get("PES_FANTASIA_APELIDO"),
                    "cpf_cnpj": row.get("PES_CNPJ_CPF"),
                    "ie_rg": row.get("PES_IE_RG"),
                    "endereco": row.get("PES_ENDERECO"),
                    "complemento": row.get("PES_COMPLEMENTO"),
                    "numero": row.get("PES_NUMERO"),
                    "bairro": row.get("PES_BAIRRO"),
                    "cidade": row.get("PES_CIDADE"),
                    "cep": row.get("PES_CEP"),
                    "telefone": row.get("PES_TELEFONE"),
                    "fax": row.get("PES_FAX"),
                    "celular": row.get("PES_CELULAR"),
                    "email": row.get("PES_EMAIL"),
                    "contato": row.get("PES_CONTATO"),
                    "observacao": row.get("PES_OBSERVACAO"),
                    "dt_cadastro_pessoa": str(row.get("PES_DT_CADASTRO")) if row.get("PES_DT_CADASTRO") else None,
                    "dt_nascimento": str(row.get("PES_DT_NASCIMENTO")) if row.get("PES_DT_NASCIMENTO") else None,
                    "status_pessoa": row.get("PES_STATUS"),
                    "cliente": row.get("PES_CLIENTE"),
                    "fornecedor": row.get("PES_FORNECEDOR"),
                    "vendedor": row.get("PES_VENDEDOR"),
                    "colaborador": row.get("PES_COLABORADOR"),
                    "transportador": row.get("PES_TRANSPORTADOR"),
                    "sexo": row.get("PES_SEXO"),
                    "profissao_pessoa": row.get("PES_PROFISSAO"),
                    "ultima_alteracao": str(row.get("PES_ULTIMA_ALTERACAO")) if row.get("PES_ULTIMA_ALTERACAO") else None,
                    "guid": row.get("PES_GUID"),
                },
            }
        )

    return dados
