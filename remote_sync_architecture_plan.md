# Evolução da Arquitetura do Projeto SaaS - Painel LMD

# Arquitetura Inicial Proposta

## Objetivo Inicial

A proposta inicial do projeto era substituir a sincronização atual baseada em arquivos JSON agrupados por um sistema de sincronismo remoto utilizando bancos SQLite isolados por cliente (“database-per-tenant”).

O objetivo principal era permitir que o backend utilizasse diretamente a camada de `repositories` já existente, sem precisar reescrever consultas, filtros, paginações e gráficos do dashboard.

A ideia original buscava:

* Reduzir retrabalho no backend
* Reaproveitar queries existentes
* Facilitar a migração do ambiente local para SaaS
* Permitir sincronização remota sem VPN ou abertura de portas
* Utilizar um banco intermediário leve e compatível com SQLAlchemy

---

# Funcionamento da Arquitetura Inicial

## 1. Agente de Sincronismo (`agent.py`)

Inicialmente, o agente seria responsável por:

* Ler tabelas do Firebird local
* Identificar registros alterados nas últimas 24h/48h
* Enviar os dados para a API do backend
* Não realizar regras de negócio ou agregações

Tabelas previstas:

```txt
TB_PEDIDO_VENDA
TB_RECEBIMENTO
TB_PAGAMENTO
TB_USUARIO
```

---

## 2. Banco Central em SQLite

Cada cliente teria seu próprio banco SQLite no servidor:

```txt
sync_data/46512675000110.db
```

A API abriria dinamicamente o banco correto e faria:

```txt
INSERT
UPDATE
UPSERT
```

---

## 3. Roteamento Inteligente

O backend decidiria automaticamente qual banco utilizar:

### Cliente Local

```python
engine = create_engine(firebird://...)
```

### Cliente Remoto

```python
engine = create_engine(sqlite:///sync_data/cnpj.db)
```

A camada `repositories` permaneceria transparente para o restante da aplicação.

---

## 4. Matriz e Filiais

Foi planejado um sistema de agrupamento utilizando:

```json
"sync_group": "CNPJ_MATRIZ"
```

Empresas compartilhando o mesmo Firebird utilizariam o mesmo banco SQLite na nuvem, enquanto os filtros SQL por `EMP_ID` manteriam os dados separados.

---

# Limitações Identificadas na Arquitetura Inicial

Durante a evolução do projeto, foram identificados alguns riscos técnicos importantes:

## 1. SQLite Limitaria o Crescimento do SaaS

Embora fosse simples para MVP, o SQLite apresentaria limitações futuras:

* concorrência
* escalabilidade
* backups
* múltiplas conexões simultâneas
* analytics avançado
* dashboards pesados

---

## 2. Compatibilidade Firebird x SQLite

Foi identificado que reutilizar os repositories diretamente poderia gerar problemas futuros devido às diferenças SQL entre os bancos:

* funções SQL
* manipulação de datas
* casts
* procedures
* tipos numéricos
* performance
* collation

---

## 3. Sincronismo Baseado em Janela de Tempo

O modelo de “últimas 24h/48h” apresentava riscos:

* duplicidade
* timezone
* relógio incorreto no cliente
* perda de registros

---

# Nova Arquitetura Definida (Arquitetura Atual)

Após análise da escalabilidade do produto SaaS, foi definida uma arquitetura mais robusta, inspirada em soluções como GePlug/GeSync.

---

# Objetivo Atual

Transformar o sistema em uma plataforma SaaS completa com:

* sincronismo remoto contínuo
* replicação parcial do ERP
* banco centralizado em PostgreSQL
* dashboard 100% baseado na nuvem
* suporte multi-tenant
* suporte matriz/filiais
* sincronismo incremental inteligente

---

# Nova Arquitetura SaaS

## 1. Serviço de Sincronismo no Cliente

Agora o cliente possuirá um serviço instalado localmente:

```txt
Windows Service / Agent
```

Esse serviço será responsável por:

* sincronização inicial completa
* sincronização incremental
* fila offline
* retry automático
* autenticação por token
* envio contínuo para a nuvem

---

# Fluxo do Agente

## Primeira execução

```txt
1. Cliente instala o Agent
2. Configura token/API
3. Agent autentica no backend
4. Executa FULL SYNC
5. Replica tabelas essenciais
6. Dashboard é liberado
```

---

## Próximas execuções

O Agent passará a enviar apenas alterações:

```sql
WHERE updated_at > :last_sync
```

ou:

```sql
WHERE
    updated_at > :last_updated_at
OR (
    updated_at = :last_updated_at
    AND id > :last_id
)
```

---

# Banco Central Atual

Foi decidido abandonar SQLite como banco principal e utilizar:

# PostgreSQL

Motivos:

* maior escalabilidade
* melhor concorrência
* alta performance
* suporte futuro a analytics
* maior estabilidade SaaS
* suporte a milhões de registros
* melhor suporte ao SQLAlchemy
* possibilidade futura de particionamento

---

# Estratégia de Espelhamento

Foi definido que inicialmente o sistema utilizará:

# Espelhamento 1:1

Ou seja:

```txt
Firebird:
TB_PEDIDO_VENDA

PostgreSQL:
tb_pedido_venda
```

Mantendo:

* nomes das tabelas
* estrutura semelhante
* reaproveitamento de queries
* reaproveitamento de repositories
* menor retrabalho

---

# Estrutura Multi-Tenant

Cada tabela espelhada possuirá:

```sql
tenant_id
sync_group_id
emp_id
source_updated_at
synced_at
```

Exemplo:

```sql
tb_pedido_venda
```

com separação lógica por tenant.

---

# Estratégia de Matriz e Filiais

Foi mantido o conceito de:

```json
"sync_group"
```

Exemplo:

```json
{
  "sync_group": "grupo_rr_imperio"
}
```

Permitindo que múltiplas empresas compartilhem o mesmo conjunto de dados sincronizados.

---

# Melhor Estratégia Definida

## Curto Prazo (MVP SaaS)

### Melhor escolha:

✅ PostgreSQL centralizado
✅ Espelhamento 1:1 das tabelas
✅ Agente incremental
✅ UPSERT no backend
✅ Dashboard lendo somente da nuvem
✅ SQLAlchemy
✅ FastAPI
✅ Multi-tenant lógico

---

# Médio Prazo

Após validação do SaaS:

* materialized views
* cache analytics
* otimizações de KPIs
* particionamento
* filas distribuídas
* workers assíncronos

---

# Longo Prazo

Possível evolução para:

* CDC avançado
* Kafka
* Debezium
* Data Warehouse
* Event Streaming

Sem necessidade de alterar a base atual.

---

# Arquitetura Final Recomendada

```txt
Firebird Cliente
        ↓
Remote Sync Agent
        ↓
FastAPI Sync API
        ↓
PostgreSQL Centralizado
        ↓
Repositories
        ↓
Dashboard React
```

---

# Decisão Técnica Final

A melhor estratégia para o projeto neste momento é:

✅ Utilizar PostgreSQL desde o início
✅ Espelhar inicialmente as tabelas do ERP com os mesmos nomes
✅ Criar sincronismo incremental robusto
✅ Centralizar toda leitura do dashboard na nuvem
✅ Utilizar separação lógica por tenant/sync_group
✅ Manter o Agent apenas como ETL simples
✅ Evoluir posteriormente para camada analítica otimizada

Essa abordagem reduz drasticamente o tempo de desenvolvimento, facilita homologação, permite crescimento gradual do SaaS e mantém compatibilidade com o sistema atual.
