# Revisão visual V2

Referências: imagens e navegação observada no painel GePlug, sem acesso ou
incorporação do código proprietário. Cores, densidade e organização comuns foram
aplicadas às telas do PIGO; Equipe e Performance mantêm suas telas originais.
A equivalência visual de cada tela ainda deve ser avaliada na prévia pelo usuário.

Fechamento de caixa: metadados compactos, oito abas em formato de pílulas,
resumo colorido, tabela compacta, TOTAL GERAL e Excel/PDF por aba. Valores sem
fonte confirmada permanecem indisponíveis. Débitos/créditos físicos não são
renomeados como entrada/saída sem homologar a regra do ERP.

Gestão: personalizar blocos em Vendas, Financeiro, Estoque, Consolidado, Clientes,
Curva ABC e Metas. Mostrar/ocultar, reordenar por arraste ou setas, trocar tipos
compatíveis, restaurar e mostrar todos. Preferências por usuário, tenant, empresa
e tela, salvas no navegador. Não são sincronizadas entre computadores.

Cadastros: um grupo com Pessoas, Produtos e Diversos. Menu lateral recolhível,
ícones distintos e tipografia consistente. Acesso é um módulo próprio.

A análise do vendedor distingue colaborador/pessoa de usuário ERP. A auditoria
usa o vínculo USU_VENDEDOR (ou AUD_VENDEDOR quando disponível), preservando o
filtro da empresa. Ausência do vínculo é informada e não substituída por ID igual.
O agente recebeu campos opcionais de vínculo e de colaborador; atualizar e
homologar esse agente no Windows é uma etapa posterior, sem instalador nesta entrega.

Mapas: Leaflet, OpenStreetMap e catálogo MIT de municípios com códigos IBGE.
Pontos representam centros municipais, não endereços pessoais ou GPS. Municípios
homônimos sem identificação suficiente não são colocados arbitrariamente. O mapa
de Vendas mostra pedidos faturados; o financeiro mostra clientes com títulos no
recorte selecionado. Consultas atualizam a cada minuto e ao voltar à janela.
Isso reflete a última sincronização do agente, sem prometer GPS ou latência zero.
O carregamento real das ruas depende de acesso a tile.openstreetmap.org. A rede
da nuvem bloqueou essa conexão; o estado de indisponibilidade foi testado.
Na prévia os dados são fotografias sintéticas, e não atualizações do ERP.

A Análise de Aging foi renomeada para Análise de Inadimplência. Relatórios com
IA mantêm o mecanismo existente; na prévia apenas o exemplo documentado pode
ser reproduzido. Gravação pelo agente, regras de estoque e módulos dependentes
de regras não recebidas do ERP continuam sujeitos à homologação descrita nos
documentos de integração. Esta entrega não substitui produção.
