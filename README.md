# PIGO — execução da prévia compilada

[**Baixar PIGO-previa-execucao-v1.zip**](PIGO-previa-execucao-v1.zip) → Download raw file.
[Arquivos exatos do pacote](execucao) · [Verificação complementar](verificacao-antivirus.json).

O pacote contém somente os35 arquivos realmente usados pela prévia, mais
instruções e manifesto. O servidor, painel compilado e amostras são byte a byte
iguais aos usados na V3 testada. Os fontes completos, que antes estavam misturados
com a execução, ficaram separados desta distribuição.

O Windows apontou reportConfig.js nos fontes de V2 e V3. Esse alerta continua
pendente de análise; ambas as entregas foram retiradas. Não foram criadas
exclusões nem desativada a proteção. Este pacote de execução também precisa
ser aceito e verificado pelo antivírus no Windows antes de ser executado.
A varredura complementar não substitui o Microsoft Defender.

# PIGO — pacote de execução da prévia

Este pacote contém o painel React compilado, o servidor local previa.py,
os dados sintéticos e as exportações de exemplo. São os mesmos arquivos de
execução testados na revisão V3, conferidos byte a byte. Não há recompilação,
ofuscação, codificação ou mudança de formato dos arquivos executados.

Os fontes de desenvolvimento, testes, backend completo, migrações e agente
ficam separados da distribuição de execução. O Windows apontou um arquivo
nesses fontes nas entregas V2/V3, que foram retiradas. O alerta do fonte continua
pendente de análise pelo Microsoft Defender. Esta separação não confirma falso
positivo nem garante liberação pelo antivírus. A verificação do novo pacote
no Windows continua obrigatória, com a proteção ativa; se houver detecção,
mantenha o bloqueio e informe o nome da ameaça e o membro afetado.

## Abrir na VM

Extraia a pasta PIGO-PREVIEW deste ZIP em C:\Projetos, resultando em
C:\Projetos\PIGO-PREVIEW\previa.py. Verifique a pasta com o antivírus.
Após a verificação terminar sem alerta, no PowerShell da VM:

```powershell
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-PREVIEW\previa.py' --port 4021
```

Abra http://127.0.0.1:4021/login no navegador da VM.
CNPJ fictício 00000000000191, usuário demo, senha demo.
O processo fica nesse terminal; Ctrl+C encerra somente esta prévia.
Se a porta estiver ocupada, o servidor para sem encerrar outros processos.

## Recursos e limites

Menu Cadastros agrupado, lateral recolhível, personalização de blocos em sete
dashboards Gestão, revisão do caixa e suas oito abas com Excel/PDF, módulo
Acesso para avaliar usuários/perfis/permissões, correção da análise do vendedor,
Análise de Inadimplência e relatórios IA preservados.

Não se conecta a ERP, banco ou produção. As consultas são fotografias sintéticas;
mudar o período não recalcula esses dados. Gravações de usuários, metas,
cadastros e relatórios são bloqueadas. Preferências visuais são salvas neste
navegador por usuário/empresa/tela. O exemplo de IA disponível é exatamente
“Vendas por produto deste mês”; outros pedidos informam a limitação.

O mapa usa centros municipais IBGE e OpenStreetMap, que requer acesso à internet.
A rede desta nuvem bloqueou as ruas; o estado de indisponibilidade foi testado.
A implantação com dados reais e a homologação do agente são etapas distintas.
Nenhuma pasta, tarefa, banco, configuração do Caddy ou domínio da produção muda
ao executar esta prévia. Não extraia sobre a pasta P.I.G.O atual.
