# Correção da sincronização de bases grandes — 27/10/2026

[Baixar o pacote ZIP](PIGO-Sync-20261027-fontes.zip) · [Instruções e comandos](LEIA-ME.txt) · [Fontes para revisão](fontes/)

A primeira carga envia todo o histórico das tabelas suportadas em lotes de até 500 registros. Os lotes confirmados ficam registrados localmente, permitindo retomada após falhas. Os próximos ciclos comparam assinaturas e enviam somente registros novos ou alterados, incluindo alterações antigas. A leitura do ERP ainda percorre as tabelas; não foram criados triggers no Firebird.

Inclui proteção contra ciclos duplicados, recibos transacionais no PostgreSQL, preservação das chaves físicas das empresas e um painel local com percentual. O recebimento usa consultas agrupadas e executa o SQL síncrono fora do event loop da API.

## Instalação

Siga a ordem do LEIA-ME: identificar a instalação do cliente e encerrar pelo menu Sair; atualizar primeiro o backend da VM; atualizar o agente; reabrir o aplicativo e acompanhar a primeira carga. O atualizador verifica os arquivos existentes e faz backup antes de reiniciar somente a API PIGO.

## Validação

88 testes passaram no ambiente de desenvolvimento. A carga de teste com 12 mil registros usou 24 lotes; o ciclo sem alterações enviou zero registros; uma alteração antiga e três inclusões geraram apenas quatro envios. Windows, Firebird e a base real de 6 GB precisam da validação descrita nas instruções.

Este diretório contém a entrega para instalação e revisão. A publicação desta branch não instala mudanças nos computadores nem altera a branch principal.
