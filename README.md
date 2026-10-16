# PIGO — ajustes finais da prévia

[**Baixar PIGO-previa-execucao-v2.zip**](PIGO-previa-execucao-v2.zip) → Download raw file.

- Setas vetoriais para expandir/recolher os grupos, com rotação e foco por teclado.
- Menu lateral com fonte, tamanho, cores e ícones iguais ao mudar de Gestão para Equipe e Performance.
- Resumo de Inadimplência mais compacto, com os três indicadores preservados.
- Sete painéis Gestão com faixas de indicadores separadas de gráficos/tabelas.
- Estoque: seis indicadores equilibrados, sem esticar junto das tabelas.
- Tabelas maiores e análise de inadimplência em largura inteira.
- Corrigida estrutura dos blocos configuráveis em Metas e Curva ABC.
- Validado em35 combinações de painel/largura, com personalização e ordem preservadas.
- Sem mudanças na lógica de negócio de Equipe/Performance ou na produção.

## Imagens sintéticas

[Menu em Equipe](imagens/funcionarios-menu.png) · [Menu em Performance](imagens/performance-menu.png) · [Inadimplência compacta](imagens/inadimplencia-compacta.png) · [Estoque revisado](imagens/estoque-layout-1587.png) · [Financeiro revisado](imagens/financeiro-layout-1587.png)

[Alterações de código para revisão](alteracoes) · [Verificação complementar](verificacao-antivirus.json)

# PIGO — prévia de execução, revisão 2

Ajustes solicitados: setas SVG para expandir/recolher grupos e estilo único
na lateral, inclusive Equipe e Performance. Resumo de Inadimplência mais compacto. Indicadores em faixas próprias, separados
dos gráficos e tabelas, com distribuição responsiva nos sete painéis de Gestão.
Tabelas maiores em largura inteira; corrigidos agrupamentos de Metas/Curva ABC.
Estrutura e funcionalidades internas de Equipe e Performance preservadas.

Extraia a pasta PIGO-PREVIEW-v2 em C:\Projetos, sem substituir a prévia anterior.
Mantenha o Defender ativo e verifique o ZIP e a pasta antes de executar.
O pacote contém apenas painel compilado, servidor local e amostras sintéticas.
O alerta anterior em fontes de desenvolvimento continua sem diagnóstico conclusivo;
uma varredura complementar não confirma liberação pelo Microsoft Defender.

Após verificar sem alertas, no PowerShell da VM:

```powershell
& 'C:\Projetos\P.I.G.O\backend\venv\Scripts\python.exe' 'C:\Projetos\PIGO-PREVIEW-v2\previa.py' --port 4022
```

Abra http://127.0.0.1:4022/login no navegador da VM.
CNPJ 00000000000191, usuário demo, senha demo.
Ctrl+C encerra somente esta prévia. Porta ocupada faz o servidor parar sem
encerrar processos. Nenhuma alteração na produção, ERP, banco ou Caddy.

Amostras fictícias; filtros não recalculam os snapshots. Gravações bloqueadas.
Personalização visual salva no navegador. IA oferece apenas o exemplo
“Vendas por produto deste mês”. O mapa usa centros municipais, não GPS;
ruas OpenStreetMap exigem internet. Implantação real e agente ainda dependem
homologação e compatibilidade da versão atual da VM.
