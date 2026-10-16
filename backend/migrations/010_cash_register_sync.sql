BEGIN;

CREATE TABLE IF NOT EXISTS public."TB_FECHAMENTO_CAIXA" (
    tenant_id text NOT NULL,
    erp_company_id text NOT NULL,
    "FCX_EMPRESA" text NOT NULL,
    "FCX_ID" text NOT NULL,
    "FCX_STATUS" text,
    "FCX_CAIXA" text,
    "FCX_CAIXA_DESTINO" text,
    "FCX_USU_ABERTURA" text,
    "FCX_USU_FECHAMENTO" text,
    "FCX_USU_CONFERENCIA" text,
    "FCX_DT_ABERTURA" timestamp,
    "FCX_DT_FECHAMENTO" timestamp,
    "FCX_DT_LANCAMENTO" timestamp,
    "FCX_DT_CONFERENCIA" timestamp,
    "FCX_TURNO" text,
    "FCX_VALOR_TOTAL" numeric(18,4),
    "FCX_VALOR_CAIXA" numeric(18,4),
    "FCX_VALOR_DIFERENCA" numeric(18,4),
    "FCX_VALOR_VENDA" numeric(18,4),
    "FCX_QTDE_VENDA" numeric(18,4),
    "FCX_VALOR_DESCONTO" numeric(18,4),
    "FCX_QTDE_DESCONTO" numeric(18,4),
    "FCX_VALOR_CANCELADOS" numeric(18,4),
    "FCX_QTDE_CANCELADOS" numeric(18,4),
    "FCX_VALOR_SANGRIA" numeric(18,4),
    "FCX_QTDE_SANGRIA" numeric(18,4),
    "FCX_VALOR_SUPRIMENTO" numeric(18,4),
    "FCX_QTDE_SUPRIMENTO" numeric(18,4),
    "FCX_VALOR_DEBITO" numeric(18,4),
    "FCX_VALOR_CREDITO" numeric(18,4),
    "FCX_VALOR_TROCO" numeric(18,4),
    "FCX_TROCO_PERDOADO" numeric(18,4),
    "FCX_VALOR_PRAZO" numeric(18,4),
    "FCX_VALOR_BANC" numeric(18,4),
    "FCX_OBSERVACAO" text,
    PRIMARY KEY (tenant_id, erp_company_id, "FCX_ID"),
    CHECK (erp_company_id = "FCX_EMPRESA")
);

CREATE TABLE IF NOT EXISTS public."TB_FECHAMENTO_CAIXA_ITEM" (
    tenant_id text NOT NULL,
    erp_company_id text NOT NULL,
    "FCXI_EMPRESA" text NOT NULL,
    "FCXI_FECHAMENTO" text NOT NULL,
    "FCXI_SEQUENCIA" text NOT NULL,
    "FCXI_ESPECIE_MOEDA" text,
    "FCXI_VALOR_DEBITO" numeric(18,4),
    "FCXI_VALOR_CREDITO" numeric(18,4),
    "FCXI_VALOR_TOTAL" numeric(18,4),
    "FCXI_VALOR_CAIXA" numeric(18,4),
    "FCXI_DIFERENCA" numeric(18,4),
    "FCXI_MOV_CAIXA" text,
    PRIMARY KEY (tenant_id, erp_company_id, "FCXI_FECHAMENTO", "FCXI_SEQUENCIA"),
    CHECK (erp_company_id = "FCXI_EMPRESA")
);

CREATE TABLE IF NOT EXISTS public."TB_FECHAMENTO_CAIXA_VENDA" (
    tenant_id text NOT NULL,
    erp_company_id text NOT NULL,
    "FCXV_EMPRESA" text NOT NULL,
    "FCXV_FECHAMENTO" text NOT NULL,
    "FCXV_SEQUENCIA" text NOT NULL,
    "FCXV_ESPECIE_MOEDA" text,
    "FCXV_VALOR" numeric(18,4),
    "FCXV_ORIGEM" text,
    "FCXV_VALOR_CAIXA" numeric(18,4),
    "FCXV_DIFERENCA" numeric(18,4),
    PRIMARY KEY (tenant_id, erp_company_id, "FCXV_FECHAMENTO", "FCXV_SEQUENCIA"),
    CHECK (erp_company_id = "FCXV_EMPRESA")
);

CREATE TABLE IF NOT EXISTS public."TB_MOVIMENTO_CAIXA" (
    tenant_id text NOT NULL,
    erp_company_id text NOT NULL,
    "MOV_EMPRESA" text NOT NULL,
    "MOV_ID" text NOT NULL,
    "MOV_CAIXA" text,
    "MOV_TIPO" text,
    "MOV_DT_EMISSAO" timestamp,
    "MOV_VALOR" numeric(18,4),
    "MOV_USUARIO" text,
    "MOV_DT_LANCAMENTO" timestamp,
    "MOV_STATUS" text,
    "MOV_ORIGEM" text,
    "MOV_ID_ORIGEM" text,
    "MOV_FECHAMENTO" text,
    "MOV_HISTORICO" text,
    "MOV_ESPECIE_MOEDA" text,
    "MOV_ITEM_ORIGEM" text,
    "MOV_TROCO" text,
    "MOV_ID_MOVIMENTO" text,
    PRIMARY KEY (tenant_id, erp_company_id, "MOV_ID"),
    CHECK (erp_company_id = "MOV_EMPRESA")
);

CREATE INDEX IF NOT EXISTS ix_cash_closing_history
    ON public."TB_FECHAMENTO_CAIXA"
    (tenant_id, erp_company_id, "FCX_DT_ABERTURA", "FCX_DT_FECHAMENTO", "FCX_STATUS");

CREATE INDEX IF NOT EXISTS ix_cash_closing_items
    ON public."TB_FECHAMENTO_CAIXA_ITEM"
    (tenant_id, erp_company_id, "FCXI_FECHAMENTO");

CREATE INDEX IF NOT EXISTS ix_cash_closing_sales
    ON public."TB_FECHAMENTO_CAIXA_VENDA"
    (tenant_id, erp_company_id, "FCXV_FECHAMENTO");

CREATE INDEX IF NOT EXISTS ix_cash_movements_closing_date
    ON public."TB_MOVIMENTO_CAIXA"
    (tenant_id, erp_company_id, "MOV_FECHAMENTO", "MOV_DT_LANCAMENTO");

COMMIT;
