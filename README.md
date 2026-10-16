# Prévia PIGO V3 — entrega suspensa

O usuário informou em 16/10/2026 que o navegador bloqueou o ZIP V3 com
“Vírus detectado”. O arquivo e os fontes executáveis foram retirados da árvore
atual desta branch enquanto o alerta é investigado. O histórico mantém versões
anteriores apenas para rastreabilidade; não as restaure ou execute.

O módulo reportConfig.js foi refatorado para carregar dados JSON validados,
mas o usuário informou novo bloqueio. A varredura complementar ClamAV da V3
não apresentou detecção; isso não anula a decisão do Microsoft Defender.
A atualização das assinaturas ClamAV estava indisponível nesta nuvem.
Os testes funcionais do painel não equivalem a uma validação antivírus.
O bloqueio desta V3 ainda não identifica o membro interno responsável nem
confirma falso positivo. Não desative a proteção nem crie exclusões.

As imagens abaixo são capturas do painel com dados fictícios; não executam
código do pacote. O manifesto permanece para auditoria de integridade.

- [Fechamento de caixa](imagens/fechamento.png)
- [Vendas](imagens/vendas.png)
- [Formulário de perfil](imagens/acesso-perfil.png)

Nenhuma alteração foi aplicada à VM, ao ERP, ao PostgreSQL de produção,
ao Caddy ou aos domínios. A entrega para execução continua pendente.
