# Instalação paralela da versão aprovada

Repositório confirmado pelo usuário: Suporte-Lmd-Sistemas/PIGO-DASHBOARD, main.
Base: 667934a2b938f10d4cbf55eb8c1bffae90d77556 (22/07/2026).
Os 108 arquivos de backend desta base são idênticos ao ZIP original recebido.

A entrega instalável contém backend Python, migrações e painel compilado com o
visual aprovado. Usa banco e autenticação reais após configuração; não contém
previa.py, snapshots, usuários demo ou credenciais. Não substitui o ERP nem o
instalador do agente. O código-fonte completo fica na branch de entrega;
o ZIP de execução não contém fontes de desenvolvimento React.

## Primeiro passo na VM

Baixar e verificar o ZIP com a proteção Windows ativa. Extrair a pasta
PIGO-APROVADO-20261016 em C:\Projetos, ao lado de P.I.G.O. Não extrair sobre a
produção. A porta4022 continua pertencendo à prévia visual; esta conferência
não inicia servidor nem ocupa portas.

No PowerShell da VM WIN-JG1E0O7FSBS:

```powershell
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-APROVADO-20261016\conferir_base.py' --current-root 'C:\Projetos\P.I.G.O'
```

O comando calcula hashes de app/migrações/requirements e lista diferenças com a
base declarada no GitHub. Não importa o backend nem lê o conteúdo do .env,
não se conecta ao banco, não envia dados e não altera processos ou arquivos.
BASE_CONFERE confirma somente essa igualdade. REVISAR_DIFERENCAS identifica
arquivos que precisam ser conciliados antes de qualquer substituição. A saída
pode ser compartilhada; não contém configuração ou credenciais.

## Instalação após conferir a base e o banco

1. Manter a produção em funcionamento e preservar backend/.env, JWT, parâmetros
   de licença, tarefa4010 e o Caddyfile.production completo. A pasta P.I.G.O não
   deve ser renomeada: tarefa e ambiente Python dependem dela.
2. Fazer backup PostgreSQL com a ferramenta da instalação atual e testar a
   restauração numa base de homologação. Configurar a instância nova com um .env
   próprio apontando para essa cópia, sem reutilizar produção para os primeiros
   testes. Não enviar o .env, backup ou senhas ao GitHub/chat.
3. Criar um venv próprio no backend novo e instalar requirements.txt. O pacote
   não inclui o venv antigo, Node.js ou binários baixados por terceiros. Aplicar
   migrações somente na cópia restaurada e conferir a011 de Acesso.
4. Iniciar a nova API apenas em127.0.0.1 numa porta livre confirmada. Conferir
   login ERP, licença, dados por empresa, Equipe, Performance, IA, Acesso e as
   consultas de Gestão/Financeiro. O painel deve usar /api no mesmo servidor.
5. Antes de apontar a nova instância para produção, revisar migrações aplicadas,
   backup válido e compatibilidade com sincronização do agente. Programar a troca
   somente do domínioPIGO no Caddy, mantendo os outros domínios e uma configuração
   anterior pronta para retorno. Nenhuma troca é feita por este pacote.
6. Configurar a inicialização automática da nova instância após validação. A
   tarefa antiga permanece como está até a troca e a verificação externa.

O comando de migração existente percorre os arquivos SQL. Ele não valida backup,
não detecta automaticamente deriva de schema e não deve ser executado como parte
desta primeira conferência de arquivos.

## Limites existentes que continuam explícitos

O agente recebido chama POST /api/agent/activate; essa rota não existe na base
main confirmada. Esta entrega não inventa um contrato de ativação nem substitui
o LicenseControl. Preservar a instalação e as credenciais atuais do agente;
novas ativações e o fluxo de licenciamento devem ser homologados separadamente.
A ausência da rota é uma limitação da própria base, não uma rota removida por
esta revisão.

Não atualizar automaticamente o agente nem habilitar gravações no ERP. A fila e
o executor preparados dependem dos procedimentos e regras reais de cadastro do
ERP. Consolidação de estoque por local/variação ainda depende dessa definição;
valores sem regra confirmada continuam indisponíveis. Mapas usam centros
municipais; ruas dependem da internet/OpenStreetMap. A aprovação visual não
substitui esses testes de integração.

O alerta anterior do Defender em fontes de desenvolvimento React permanece sem
adjudicação; a separação entre fontes e execução não comprova falso positivo.
Manter a proteção ativa, verificar a distribuição de execução e suspender o uso
se houver novo alerta. A varredura complementar não substitui o Defender.
