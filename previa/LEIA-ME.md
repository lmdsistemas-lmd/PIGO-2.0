# PIGO NOVO — prévia da versão mesclada

Esta V3 refatora a configuração dos relatórios para JSON com validação.
O reportConfig.js permanece no mesmo caminho e importa as definições locais.
Opções, textos e exemplos da IA são iguais aos originais, conforme testes de
contrato. A V2 foi retirada após o bloqueio do Windows. Consulte
fontes/docs/SEGURANCA_DISTRIBUICAO.md para evidências e limites da investigação.
A liberação pelo Microsoft Defender desta V3 ainda precisa ocorrer no Windows;
não restaure o pacote anterior nem desative a proteção.

Interface do PIGO ampliada a partir da comparação funcional com o painel
GePlug. O código proprietário do GePlug não foi recebido nem incorporado.
Relatórios com IA e Performance mantêm suas funcionalidades. Equipe mantém
o layout e recebeu correção na identificação e análise do vendedor. As telas novas incluem análises de
clientes/ABC/metas, cadastros de pessoas/produtos/diversos, financeiro,
fechamentos com oito abas e fluxo de caixa.

## Abrir na VM Windows

Extraia a pasta PIGO-NOVO-v3 deste ZIP em C:\Projetos. O resultado deve ser
C:\Projetos\PIGO-NOVO-v3\previa.py. Não extraia sobre a pasta P.I.G.O atual.
No PowerShell da VM:

```powershell
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-NOVO-v3\previa.py'
```

Abra http://127.0.0.1:4020/login no navegador DA VM.

- CNPJ fictício: 00000000000191
- Usuário de demonstração: demo
- Senha de demonstração: demo

O Python existente executa apenas a biblioteca padrão. Não precisa npm,
pip, PostgreSQL, Firebird, credenciais reais ou alteração no Caddy.
O processo fica neste terminal; Ctrl+C encerra somente a prévia.
Se a porta estiver ocupada, o programa para sem encerrar outro processo.
Para outra porta de teste, use --port 4021 (faixa permitida: 4020–4099).
A escuta é somente 127.0.0.1; o endereço não funciona fora da VM.

## O que esta prévia mostra

O painel React foi compilado dos fontes mesclados. O servidor previa.py
fornece amostras sintéticas de consultas reais executadas na base descartável
da nuvem. O aviso de demonstração permanece visível em todas as telas.
As consultas usam uma fotografia de dados fictícios: datas, totais e
gráficos não representam sua empresa. O mapa usa OpenStreetMap gratuito e os centros municipais IBGE. Em produção,
o financeiro consulta as atualizações sincronizadas a cada minuto e ao voltar
à aba. Nesta prévia os dados são fixos, embora o mapa real necessite internet.
Alterar o período não recalcula a
fotografia; busca/paginação de cadastros e alguns filtros locais funcionam.
Campos sem informação permanecem vazios ou indisponíveis.

Personalizar gráficos permite ocultar, reordenar e mudar tipos de gráficos
compatíveis, restaurar e mostrar todos. Preferências são salvas neste navegador
por usuário, empresa e tela. O menu lateral recolhe e guarda sua preferência.

Acesso reúne usuários, perfis e permissões próprios PIGO. Os fontes incluem
autenticação local, hashes de senha, autorização na API e revogação de sessão.
Nesta prévia os formulários podem ser avaliados, mas as gravações são bloqueadas.
A instalação completa exige conciliar/aplicar a migração 011 em homologação.

É possível abrir formulários para avaliar o layout, porém gravar metas,
cadastros e relatórios é bloqueado. Nenhuma solicitação é enviada ao agente
nem confirmada como gravada. Não existe conexão com produção ou ERP.
Exportações de cadastros nesta prévia são CSV de amostra. No fechamento,
Excel e PDF de cada aba são amostras geradas pelo backend de teste.

No assistente IA, use exatamente o exemplo:
"Vendas por produto deste mês". Nesta prévia ele reproduz o resultado
sintético e sua visualização; outros pedidos informam a limitação. Isso
não substitui o mecanismo completo de relatórios com IA do backend.

## Fontes e implantação posterior

fontes/backend e fontes/frontend contêm a implementação mesclada; fontes/remote-sync-agent
contém os fontes do agente (sem instalador); fontes/docs
registra os contratos e as pendências da integração. Não incluem configurações
ativas nem o pacote de scripts Caddy bloqueado pelo antivírus. Houve varredura
complementar ClamAV com assinaturas de 11/10/2026; ela não substitui o Defender.
Mantenha a proteção ativa; se houver bloqueio,
pare e informe o alerta, sem restaurar ou criar exclusões.

Esta entrega é para AVALIAR a interface antes de trocar o sistema em uso.
O backend completo exige seu próprio banco PostgreSQL de homologação,
configuração/licença e compatibilidade com o agente atual. Sua rota de
ativação não constava no upload original. Não copie o .env da produção nem
aplique migrações no banco atual para abrir esta prévia.

A gravação real de cadastros pelo agente permanece desativada até homologar
as regras oficiais do ERP e a geração de códigos. Estoque por locais/variações
permanece separado até confirmar sua consolidação. Nenhuma tela isolada
comprova homologação dessas regras.

Mantenha C:\Projetos\P.I.G.O com seu nome atual: a tarefa instalada aponta
para esse caminho. O PIGO atual será a versão de retorno; renomeá-lo agora
interromperia suas referências. O domínio público e o Caddy não são alterados.
Após avaliar a prévia, a implantação completa terá backup/restauração do
banco, fontes/configurações, teste isolado, conexão do agente e troca do
domínio. Renomear somente a pasta não é backup do PostgreSQL.
