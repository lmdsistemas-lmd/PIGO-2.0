# Investigação do bloqueio da prévia V2

Em 16/10/2026, o Windows apontou este membro do ZIP V2:
`PIGO-NOVO-v2/fontes/frontend/src/components/reports/reportConfig.js`.
O nome da ameaça deste novo alerta não foi informado. O alerta anterior do
pacote Caddy não identifica automaticamente a classificação deste arquivo.

O ZIP V2 foi retirado da entrega. Seu SHA256 era
`2f6086e11cd6acbe49f27ee08c318dc4f4c8ee4dd34e3294e40fb67fb0f6d2b4`.
O membro indicado tinha SHA256
`8b709441274f7cca36c691dc882959468fe30b29edb8c2363550b74bb7ee91ab`
e era byte a byte igual ao arquivo do upload original do PIGO.

A inspeção integral encontrou constantes de categorias, rótulos, tipos de
gráficos, perfis, formulário inicial, apresentação e exemplos da IA, mais
um índice de categorias derivado dessas constantes. Não encontrou acesso
a rede, arquivos, processos, downloads ou avaliação de código nesse módulo.
Uma extração por AST, sem executá-lo, confirmou que as definições eram dados
literais. Essa evidência é compatível com falso positivo, sem substituir a
classificação do Microsoft Defender.

## Alteração da aplicação

As definições passaram a `reportDefinitions.json`. `reportConfig.js` continua
no mesmo caminho como módulo de importação e exportação, com validação de
estrutura, nomes permitidos, referências de gráficos/perfis, textos e cores.
Não há avaliação de código, carregamento remoto, codificação ou ofuscação
para reconstruir o arquivo anterior. O módulo antigo não está no novo pacote.

Os testes conferem o contrato integral dos oito conjuntos de dados contra
a versão original, além das categorias derivadas e da rejeição de dados
inválidos. O SHA256 do contrato JSON original é
`29e7c540c24e41ccee392ad29291a438a5eb053073f99a54ffdf36fbe4840779`.
As opções dos relatórios e os exemplos da IA foram preservados.

## Limites da verificação

A varredura complementar local usou ClamAV 1.5.4, base daily28150 de
11/10/2026, main63 e bytecode339. Não encontrou detecção no ZIP V2 e no
arquivo isolado; também não encontrou detecção no diretório refatorado.
A tentativa de atualizar assinaturas falhou por falta de conexão ao servidor
oficial. O resultado não comprova ausência de ameaça nem invalida o Defender.
Nenhum código foi enviado a serviços externos de análise.

O pacote novo será verificado integralmente com o mesmo scanner antes da
publicação. A verificação do Microsoft Defender no Windows continua pendente.
Mantenha a proteção ativa. Antes de executar, o novo download e sua varredura
precisam terminar sem alerta. Se houver outra detecção, mantenha o bloqueio e
registre o nome da ameaça e o membro afetado; não restaure ou crie exclusões.
Não há garantia de liberação antes dessa verificação na máquina Windows.
