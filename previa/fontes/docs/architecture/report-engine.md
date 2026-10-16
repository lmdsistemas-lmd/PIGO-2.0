# Report Engine

O Report Engine executa uma `ReportDefinition` validada. Ele não interpreta linguagem natural e não recebe SQL do cliente.

Fluxo: catálogo seguro → validação → Query Builder → provider → preview ou exportação.

O catálogo é a única camada que conhece tabelas, colunas e relacionamentos físicos do ERP. APIs públicas removem essas informações.
