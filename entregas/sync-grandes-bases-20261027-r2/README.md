# PIGO Sync — revisão R2, 27/10/2026

Correção sobre os fontes fornecidos pelo cliente. O esquema real de códigos de barras não tem PRDC_EMPRESA; a empresa é consultada no produto quando sua chave é globalmente única. Sem correspondência, o valor permanece desconhecido, sem descartar o registro.

Campos e tabelas opcionais ausentes não bloqueiam outros recursos. Recursos com identidade não reconhecida são listados como indisponíveis no resultado e no painel. Erros reais de envio e persistência continuam interrompendo o lote, com retomada, sem falso sucesso.

## Instalação neste atendimento

Atualizar somente o agente no WIN-F6NF7R6I6PJ. O backend v2 já passou na verificação de compatibilidade; os três arquivos de backend incluídos são idênticos à R1. Não reinstalar o servidor nem alterar Caddy, License Control, licenças, cofre ou tokens.

Baixe o ZIP desta pasta e extraia em `C:\Temp\PIGO-Sync-20261027-r2`. Feche o Remote Sync usando Sair na bandeja e siga o início de [LEIA-ME.txt](LEIA-ME.txt). Os fontes ficam em [fontes](fontes) para revisão. O atualizador confere os hashes conhecidos antes de substituir arquivos e cria backup.

## Verificação

80 testes relevantes passaram: 7 de variantes de esquema e associação de códigos de barras, 20 do motor de sincronização, 2 de planos, 6 do atualizador e 45 de regressão. A estrutura enviada reconheceu 28 recursos compatíveis e informou quatro tabelas opcionais ausentes. Teste de associação preservou registros de três empresas e um código de barras órfão.

A execução nativa no Windows com Firebird e a primeira carga real de 6 GB ainda precisam ser verificadas no cliente. A leitura incremental ainda varre registros para comparar assinaturas; somente novos e alterados são enviados. Exclusões físicas não são propagadas. 100% indica conclusão dos recursos disponíveis nesta execução, com indisponíveis explicitamente listados.
