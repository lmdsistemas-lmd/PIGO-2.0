# Assistente de relatórios

O assistente transforma linguagem de negócio em uma `ReportDefinition` revisável. Ele não executa preview, não salva relatórios e não recebe nem produz SQL.

Fluxo da primeira versão:

1. `DeterministicIntentProvider` normaliza o texto e reconhece objetos, métricas, dimensões, períodos e filtros.
2. A Business Knowledge Layer valida disponibilidade e ambiguidades.
3. Filtros que exigem IDs são resolvidos contra opções reais do catálogo.
4. `ReportIntentToDefinitionService` escolhe uma fonte compatível e monta a definição pública.
5. `ReportQueryBuilder.validate()` valida o contrato sem montar SQL.
6. O frontend apresenta o entendimento e exige confirmação antes de abrir o Builder ou gerar preview.

Segurança: autenticação obrigatória, isolamento pelo contexto de tenant, empresa explícita, permissão por categoria, prompt de até 1.000 caracteres, rate limit, bloqueio de instruções técnicas, request ID e auditoria por hash. Valores livres de filtros e o prompt original não são persistidos na auditoria.

Configuração futura de LLM:

- `REPORT_AI_ENABLED=false`
- `REPORT_AI_PROVIDER=`
- `REPORT_AI_MODEL=`
- `REPORT_AI_TIMEOUT_SECONDS=15`
- `REPORT_ASSISTANT_RATE_LIMIT_PER_MINUTE=30`

Uma implementação futura deverá implementar `ReportIntentProvider` e devolver o mesmo schema. Nenhuma outra camada dependerá diretamente de fornecedor ou modelo de IA.
