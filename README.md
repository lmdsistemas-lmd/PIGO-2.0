# P.I.G.O Dashboard

Dashboard SaaS multi-tenant para análise de dados sincronizados do ERP do cliente.

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
