# Business Knowledge Layer

A Business Knowledge Layer é o mapa de domínio acima da Semantic Layer.

Ela contém:

- objetos como Venda, Cliente, Produto, Recebimento e Vendedor;
- relações navegáveis entre esses objetos;
- métricas reutilizáveis e suas dependências;
- vocabulário e sinônimos usados para interpretar linguagem de negócio;
- validação de disponibilidade, dependências e ambiguidades.

O parser de intenção é determinístico nesta fase. Ele não executa relatórios e não gera SQL. Uma futura integração com LLM deverá produzir somente intenção estruturada, sujeita ao validador e à confirmação do usuário.
