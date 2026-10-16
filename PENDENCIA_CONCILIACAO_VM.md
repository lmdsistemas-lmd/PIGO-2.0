# Instalação suspensa para conciliar os fontes da VM

A conferência executada pelo usuário em WIN-JG1E0O7FSBS encontrou 60 arquivos iguais,
48 alterados e 5 módulos Python adicionais em relação à main do GitHub. Entre os
adicionais estão ativação do agente, caixa e resolução de coordenadas municipais.
A versão em execução possui diferenças concretas que precisam ser preservadas.

O ZIP de instalação derivado apenas da main foi retirado desta branch antes da
instalação. Seu hash e verificações anteriores permanecem para auditoria. Os
fontes preparados nesta branch continuam em revisão; não representam uma versão
já conciliada com a VM. A prévia visual aprovada e sua referência fixa permanecem
preservadas no repositório.

Próximo passo: obter os arquivosPython de backend/app e backend/scripts,
SQL de backend/migrations e backend/requirements.txt da VM. O coletor abaixo
somente lê esses arquivos e cria um ZIP novo em TEMP; não importa módulos do
backend nem acessa .env, banco, processos, Caddy ou o ambiente virtual.

[Coletor em código aberto](deploy/manual/coletar_fontes_vm.py) ·
[Resultado da conferência recebido](distribuicao/conferencia-vm.json).

Depois de receber os fontes, conciliar especialmente configuração, modelos,
licenciamento/ativação, sincronização e caixa; integrar o painel aprovado e as
novas APIs mantendo as diferenças da VM. Validar em ambiente isolado e preparar
nova distribuição antes de qualquer instalação ou alteração de roteamento.
