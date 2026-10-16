> **Backend conciliado com os 129 arquivos recebidos da VM.**
> [Baixar aplicação conciliada](distribuicao/PIGO-vm-conciliado-20261016.zip) → Download raw file.
> [Conciliação e testes](docs/CONCILIACAO_BACKEND_VM.md) · [Primeiro passo na VM](docs/INSTALACAO_VERSAO_APROVADA.md).
> O pacote contém backend real e painel compilado com o layout aprovado.
> A instalação em produção ainda não foi realizada. O primeiro comando somente inspeciona o ambiente.
> Manter o Defender ativo. A varredura complementar não substitui a verificação no Windows.

# P.I.G.O Dashboard

Dashboard SaaS multi-tenant para análise de dados sincronizados do ERP do cliente.

Veja as análises adicionadas, os módulos preservados e a validação em [Integração das análises](docs/INTEGRACAO_GEPLUG.md).

A ampliação de Gestão, Financeiro, Caixa e Cadastros está descrita no [comparativo operacional](docs/COMPARATIVO_OPERACIONAL.md). As solicitações de cadastro/edição passam pelo remote sync agent; [o adaptador de negócio do ERP](docs/GRAVACAO_ERP.md) ainda precisa ser configurado e homologado para habilitar gravações reais.

O agente e o desktop atuais estão integrados conforme [AGENTE_ATUAL.md](docs/AGENTE_ATUAL.md), incluindo exportação da estrutura do ERP, contratos físicos do caixa e conservação das sequências de itens/parcelas.

A versão visual aprovada e a instalação paralela na VM Windows Server estão descritas em [Instalação da versão aprovada](docs/INSTALACAO_VERSAO_APROVADA.md). A tarefa existente na porta 4010 e o Caddy com vários domínios devem ser preservados até a conferência da nova instância.

## Arquitetura Atual

- `frontend`: aplicação React/Vite do dashboard.
- `backend`: API FastAPI do P.I.G.O.
- `remote-sync-agent`: agente instalado no ambiente do cliente para enviar dados do ERP.

## Licenciamento e Tenants

O P.I.G.O. não possui controle local de licença.

A fonte única da verdade para empresa, licença, acesso, status, expiração e API Token é o License Control externo. O fluxo oficial é:

License Control externo -> `/api/internal/license-control/tenants/sync` -> tabelas
`tenants`/`companies` -> frontend P.I.G.O.

A rota antiga `/api/internal/license-control/sync-tenant` permanece como adaptador
para a versão atual do `PigoIntegrationService.ts`.

No backend, configure o mesmo segredo de `PIGO_INTEGRATION_TOKEN` em:

```env
LICENSE_CONTROL_INTEGRATION_TOKEN=<segredo-compartilhado>
```

Para aplicar as migrations e iniciar a API local na porta esperada pela integração:

```powershell
cd backend
python -m scripts.apply_migrations
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

O frontend Vite usa a porta `5176`. Pelo domÃ­nio pÃºblico, todas as
requisiÃ§Ãµes ao backend usam caminhos relativos sob `/api`.

O P.I.G.O. deve usar somente:

- `tenants`;
- dados sincronizados pelo License Control externo;
- API Token vinculado ao tenant;
- dados recebidos pelo `remote-sync-agent`.

Nenhum painel administrativo interno faz parte da arquitetura atual.
