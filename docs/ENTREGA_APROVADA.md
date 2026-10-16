# Entrega visual aprovada — PIGO

Em 16/10/2026 (America/Araguaina), o usuário aprovou a revisão com:
“perfeito. podemos finalizar”. A aprovação se refere à prévia visual avaliada.

O pacote aprovado é **PIGO-previa-execucao-v2.zip**, SHA256:

`d509c1847b7d49207c3c6672642c111471b6980aad551f6b3b3d22a1c6dca731`

[Baixar o pacote aprovado](PIGO-previa-execucao-v2.zip) ·
[Registro da aprovação](aprovacao.json) ·
[Conferência dos layouts](verificacao-layouts.json) ·
[Varredura complementar e seus limites](verificacao-antivirus.json).

## Concluído nesta etapa

- Menu com Cadastros e subdivisões, ícones distintos, setas SVG e lateral recolhível.
- Fonte, dimensões e cores da lateral mantidas em Equipe e Performance.
- Sete painéis Gestão com personalização de blocos; preferências isoladas por usuário/empresa/tela.
- Distribuição responsiva: indicadores em linhas próprias, tabelas maiores em largura inteira,
  sem cartões esticados pela altura de gráficos/tabelas; agrupamentos corrigidos em Metas/ABC.
- Inadimplência compacta e Análise de Inadimplência preservada.
- Revisão de Fechamento de Caixa, oito abas e exportações sintéticas Excel/PDF.
- Interface de Acesso para usuários, perfis e permissões do próprio PIGO.
- Correção da identidade do vendedor na análise, mapa municipal e relatórios IA preservados.

Compilação e ESLint dos componentes alterados passaram. A prévia passou em 11
conjuntos funcionais/HTTP, 33 telas e 35 combinações dos sete painéis com cinco
larguras de tela. Ocultar, reordenar, restaurar e manter preferências após recarregar
foram conferidos, inclusive ao intercalar tabelas entre indicadores. Os testes
usam dados sintéticos; não são homologação do ERP real.

## Execução da prévia

O pacote e suas instruções permanecem os mesmos: pasta
`C:\Projetos\PIGO-PREVIEW-v2`, porta 4022 e login fictício
CNPJ 00000000000191, usuário demo, senha demo. Proteção Windows ativa; verificar
antes de executar. Nenhum ZIP foi recompilado ou reempacotado para registrar
esta aprovação. Não substituir `C:\Projetos\P.I.G.O` pela prévia.

## Conciliação e instalação

O backend atual da VM foi recebido e conciliado. A rota de ativação e a API de
caixa em execução foram preservadas, junto às mudanças do painel aprovado.
Veja [Conciliação do backend](CONCILIACAO_BACKEND_VM.md) e
[Instalação da versão aprovada](INSTALACAO_VERSAO_APROVADA.md).

A próxima etapa é inspecionar a VM e validar backup/restauração e a instância
paralela. A produção ainda não foi alterada. Gravações pelo agente e a regra
de consolidação de estoque continuam dependendo da homologação do ERP.
