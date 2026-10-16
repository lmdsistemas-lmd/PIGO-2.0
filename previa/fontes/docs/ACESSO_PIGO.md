# Acesso: contas próprias do PIGO

O módulo administra usuários, perfis e permissões do PIGO, separados dos usuários
sincronizados do ERP. Nenhuma operação deste módulo envia alterações ao Firebird.
A licença da empresa continua obrigatória.

Na primeira configuração em homologação, entre com o administrador ERP já existente,
abra Acesso → Perfis e crie um perfil com Administrar usuários e perfis do PIGO.
Crie então uma conta em Acesso → Usuários. Para usá-la, escolha Conta PIGO no login.
Não existe senha administrativa padrão no backend completo.

Os perfis são isolados por tenant. Cada API verifica a permissão correspondente;
ocultar o menu é apenas uma conveniência visual. Permissões e estado do usuário
são consultados em cada requisição autenticada com conta PIGO. Desativar uma conta
revoga suas sessões, inclusive se ela for reativada depois. Trocar a senha também
revoga tokens anteriores. A interface impede remover a própria administração.

Senhas são armazenadas com PBKDF2 e salt aleatório; os endpoints nunca retornam
senhas ou hashes. Alterações de usuários e perfis geram registro de auditoria,
com tenant e autor, sem senha. Dados financeiros em relatórios exigem também
finance.read, mesmo quando outra permissão de edição foi atribuída.

A migração 011_pigo_access.sql é proposta para homologação. Antes de implantação,
concilie sua numeração e o schema com a versão efetivamente instalada na VM,
faça backup do PostgreSQL e teste restauração e compatibilidade. A prévia visual
não aplica migrações, cria contas reais ou usa o banco de produção.

Na prévia, todos os dados são sintéticos e gravações retornam HTTP405. As telas
permitem avaliar os formulários. O backend completo está nos fontes e foi testado
separadamente com PostgreSQL descartável e duas empresas fictícias.
