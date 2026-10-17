# Atualização compacta da interface — 17/10/2026

Solicitação recebida durante a homologação na porta 4023:

- Retirar os blocos grandes de campos não enviados e explicação de estoque acima da tabela.
- Mostrar apenas uma linha discreta de última atualização, quando conhecida.
- Deixar somente o botão abaixo da logo para recolher e expandir a lateral.
- Reduzir o espaço vertical e retirar o título repetido em Relatórios.

A data exibida vem do último trabalho `COMPLETED` do tenant autenticado para
a tabela principal da consulta. Trabalhos com falha, outros tenants e a hora de
abertura/atualização da página não são usados. Se o horário não existir, a linha
é omitida. Exibição no horário local do navegador: `Última atualização: 17/10/2026 às 08:30`.
Na cópia de homologação, a data continua sendo a do último envio anterior ao backup.
Valores desconhecidos continuam como `—`; a explicação de estoque fica em Detalhes.

O cabeçalho agora organiza título e ações na mesma linha no desktop, com um
único título em Relatórios. A lateral recolhida continua com 76px e o controle
abaixo da logo permanece acessível por teclado; navegação inferior no celular
e modos Equipe/Performance são preservados.

Também foi corrigida a entrega das logos SVG, favicon e catálogo JSON de
municípios: o fallback da SPA devolvia HTML nesses endereços. As respostas
agora têm os arquivos e tipos corretos, sem expor fontes, configuração ou banco.

## Aplicar na homologação já instalada

1. Encerrar **somente o terminal da porta 4023** com Ctrl+C. Não interromper
   o Caddy, a tarefa antiga ou os outros domínios.
2. Baixar `distribuicao/PIGO-ajustes-interface-20261017.zip` pelo GitHub com a
   proteção ativa e extrair em `C:\Projetos`, substituindo os arquivos da pasta
   `PIGO-VM-CONCILIADO-20261016`. Confirmar que não criou uma pasta duplicada
   com o mesmo nome dentro da pasta atual.
3. Iniciar novamente:

```powershell
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-VM-CONCILIADO-20261016\instalar_homologacao.py' --action start
```

Manter o terminal aberto e atualizar a página da VM com Ctrl+F5.
Não executar `prepare` novamente: não há instalação de pacotes, restauração,
nova configuração ou migração para esse ajuste.

O patch contém somente o painel compilado, `backend/app/main.py`,
`backend/app/routes/operations.py`, o manifesto atualizado e o inicializador
com o novo hash do manifesto. Não contém `.env`, estado de homologação, banco,
ambiente virtual, credenciais ou fontes React. Os arquivos antigos de assets
podem permanecer para abas já abertas; o novo index referencia os novos assets.

O comando `--action start` confere os novos hashes e reaproveita a configuração
privada já instalada. Os bloqueios de sincronização/ERP permanecem ativos;
produção, Caddy e outros domínios não são alterados.

Para instalação do zero usando o ZIP base, aplicar este patch depois de extrair
o ZIP base e antes de executar o instalador atual. O arquivo `manifesto.json`
e o instalador devem ser atualizados juntos.
