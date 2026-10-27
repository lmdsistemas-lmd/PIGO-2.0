# PIGO Sync R3 — ID de registro vazio na auditoria

O diagnóstico no cliente confirmou `AUD_ID_REGISTRO` como texto vazio não nulo em `TB_AUDITORIA`. A validação anterior rejeitava o valor válido da origem. A R3 preserva o texto original no agente e no PostgreSQL, mantendo empresa, tabela e sequência na chave recebida. A exceção é restrita a esse campo; nulos e outras chaves inválidas continuam bloqueados.

## Instalação

**Servidor primeiro; cliente depois.** Feche o Remote Sync pelo menu Sair na bandeja do cliente WIN-F6NF7R6I6PJ. Extraia o ZIP desta pasta em `C:\Temp\PIGO-Sync-20261027-r3` nas duas máquinas e siga [LEIA-ME.txt](LEIA-ME.txt), com os comandos separados por computador.

Na VM WIN-JG1E0O7FSBS o atualizador confere hashes, faz backup de fontes e do PostgreSQL e reinicia somente `PigoDashboardProduction`, validando a nova capacidade. Caddy e License Control continuam em execução. No cliente, verifica a capacidade do recebimento corrigido antes de copiar os fontes. Não apaga checkpoints, cofre, configuração ou tokens; não executa migrações nem restaura banco.

## Validação

56 testes passaram, incluindo PostgreSQL real em banco isolado, IDs vazios e espaços preservados, três empresas e sequências distintas, rejeição atômica de nulos, repetição de lote sem desfazer edição nova, retomada de checkpoints R2, lote pendente após perda de resposta e envio incremental. Os hashes do pacote e a sintaxe dos comandos PowerShell foram conferidos. A execução nativa no Windows e a carga real continuam dependendo da validação local.

Não muda o escopo nem o formato dos checkpoints: as tabelas concluídas continuam confirmadas; a tabela pendente confere assinaturas e envia apenas registros ainda não confirmados ou alterados. A leitura incremental continua sendo uma varredura; exclusões físicas não são propagadas. Recursos opcionais ausentes são listados, sem bloquear os disponíveis. O painel não representa recursos indisponíveis como dados sincronizados.

Os fontes revisáveis estão em [fontes](fontes). Nenhuma credencial, configuração privada ou estrutura do cliente foi incluída.
