# PIGO Remote Sync Agent

Este diretório contém a versão atual enviada pelo usuário, integrada ao dashboard e ao desktop Electron. Preserva o cofre de credenciais, os drivers Firebird, o proprietário de execução único, o serviço Windows e a comunicação IPC autenticada.

Consulte [AGENTE_ATUAL.md](../docs/AGENTE_ATUAL.md) para configuração, compatibilidade e pendências da ativação. Consulte [GRAVACAO_ERP.md](../docs/GRAVACAO_ERP.md) para o contrato de gravação.

## Diagnóstico para concluir a integração

O arquivo `export_schema.py` funciona também com o agente original recebido. Copie apenas esse arquivo para a pasta do agente já instalado e execute:

```powershell
.\venv\Scripts\python.exe .\export_schema.py
```

Ele gera `schema_diagnostics.json` e informa o caminho completo, normalmente em `C:\ProgramData\PIGO Remote Sync\diagnostics`. São exportados somente metadados: campos, tipos, obrigatoriedade, chaves, nomes de geradores/triggers e parâmetros de procedimentos. Não lê registros comerciais, não altera o ERP e não inicia sincronização ou ativação.

Na versão integrada também há `agent.py --export-schema` e o botão **Teste → Exportar estrutura do ERP** no desktop.

## Configuração atual

Quando existe `config.json` em `C:\ProgramData\PIGO Remote Sync` (ou `PIGO_REMOTE_SYNC_DATA_DIR`), o modo desktop usa esse arquivo e o cofre `credentials.dat`. Senha Firebird, chave de licença e token permanecem protegidos com DPAPI LocalMachine no Windows. Sem configuração desktop, o modo legado usa os nomes de `.env.example` e o cofre compatível. Não envie esses arquivos de credenciais ao repositório.

O agente atual oferece `--owner`, `--activate`, `--reactivate`, `--diagnose`, `--test-firebird`, `--sync-once`, `--export-schema` e os testes IPC já existentes. A rota de ativação `/api/agent/activate` precisa ser confirmada no backend correspondente; ela não veio no backend inicial desta tarefa.

## Caixa e gravação

As tabelas físicas FCX/FCXI/FCXV/MOV e as sequências PEVI/PEVF foram mantidas. O backend reconhece essas chaves para conservar linhas repetidas. O formato operacional normalizado de movimentos usa `TB_PIGO_CAIXA_MOVIMENTO` para evitar confundir movimentos com os itens financeiros físicos do fechamento.

A fila de cadastros roda no worker do proprietário, respeita pausa e usa o mesmo token/cabeçalho de instalação. A gravação permanece desativada por padrão: depende de procedimento de negócio específico e homologado para o ERP. Não executa SQL recebido do PIGO nem substitui uma confirmação no ERP por edição local do espelho.

## Testes na nuvem

```bash
PIGO_REMOTE_SYNC_DATA_DIR=/workspace/.local/pigo-agent-tests API_TOKEN=test-agent-token COMPANY_CNPJ=00000000000191 API_BASE_URL=https://pigo.example.invalid/api python -m unittest
```

Esses valores são fictícios e as chamadas da suíte unitária são simuladas. A exportação e o executor também foram testados em Firebird descartável; isso não homologa as regras de negócio do cliente. DPAPI e IPC reais exigem Windows e os runtimes da instalação.
