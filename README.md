# Sistema de Gestão de Estoque — Apache Cassandra

**Trabalho Acadêmico — Banco de Dados Não Relacionais**

## Integrantes

| Nome | RA |
|------|----|
| Gabriel do Nascimento Rodrigues | 000154979 |
| Fernanda Rebelatto Miranda | 0900170399 |
| Guilherme Guerra de Paulo | — |
| João Vitor Ferreira da Silva | 000155066 |
| Rodrigo Barreiros Moreira | — |

## Banco Escolhido

**Apache Cassandra 4.1** — banco de dados NoSQL orientado a colunas, distribuído e de alta disponibilidade.

---

## Pré-requisitos

| Ferramenta | Versão mínima |
|------------|---------------|
| Docker     | 24.x          |
| Docker Compose | 2.x       |
| Python     | 3.10+         |
| pip        | 23+           |

---

## Instruções de Execução

### 1. Subir o Cassandra via Docker

```bash
docker compose up -d
```

Aguarde aproximadamente 60–90 segundos para o Cassandra inicializar completamente.  
Verifique com:

```bash
docker logs cassandra_estoque --tail 20
```

Quando aparecer `"state jump to NORMAL"` o cluster está pronto.

### 2. Criar o Schema

```bash
docker cp ./scripts/schema.cql cassandra_estoque:/tmp/schema.cql
docker exec -i cassandra_estoque cqlsh -f /tmp/schema.cql
```

> **Git Bash:** prefixe ambos os comandos com `MSYS_NO_PATHCONV=1` para evitar tradução de caminhos.

### 3. Inserir Dados de Seed

```bash
docker cp ./scripts/seed.cql cassandra_estoque:/tmp/seed.cql
docker exec -i cassandra_estoque cqlsh -f /tmp/seed.cql
```

> **Git Bash:** prefixe ambos os comandos com `MSYS_NO_PATHCONV=1`.

> **Por que não usar pipe (`< arquivo.cql`)?** O shell do Windows converte a codificação antes de o arquivo chegar ao container, corrompendo caracteres acentuados silenciosamente (ex.: `"Armazém"` vira `"Armaz??m"`). O `docker cp` copia o arquivo bruto diretamente, preservando o UTF-8.

### 4. Instalar Dependências Python

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Iniciar a Aplicação Flask

```bash
cd app
python app.py
```

Acesse: **http://localhost:5001**

---

## Estrutura de Arquivos

```
.
├── docker-compose.yml          # Cluster Cassandra
├── scripts/
│   ├── schema.cql              # Keyspace, tabelas, UDT, índices
│   └── seed.cql                # Dados de exemplo (20+ registros/entidade)
├── app/
│   ├── cassandra_client.py     # Conexão com o cluster
│   ├── queries.py              # Todas as queries CQL comentadas
│   └── app.py                  # Flask — rotas CRUD e API
├── templates/
│   ├── index.html              # Dashboard com KPIs
│   ├── produtos.html           # CRUD de produtos
│   ├── movimentacoes.html      # Entradas e saídas
│   ├── fornecedores.html       # Cadastro de fornecedores
│   └── consultas.html          # Consultas complexas com explicação
└── static/
    └── style.css               # Design system completo (tokens Stripe HDS)
```

---

## Fundamentação Teórica

### Tipo do Banco

O Apache Cassandra é um banco de dados **Colunar** (Wide-Column Store). Os dados são organizados em tabelas com linhas e colunas, mas diferente do modelo relacional, cada linha pode ter conjuntos diferentes de colunas e as colunas são agrupadas em famílias — otimizado para leitura e escrita em larga escala.

### Teorema CAP

O Cassandra é classificado como **AP** (Disponibilidade + Tolerância a Partição):

- **Disponibilidade** — o banco continua respondendo mesmo com falhas em nós da rede
- **Tolerância a Partição** — o sistema funciona mesmo que parte dos nós fique inacessível
- **Consistência** — é eventual (não imediata). O Cassandra permite configurar o nível de consistência por query (`ONE`, `QUORUM`, `ALL`), mas por padrão prioriza disponibilidade em vez de consistência forte

### Casos de Uso

**Quando utilizar:**
- Alta taxa de escrita (logs, movimentações, eventos em tempo real)
- Dados com padrão de acesso previsível (query-first design)
- Escalabilidade horizontal sem ponto único de falha
- Sistemas distribuídos geograficamente

**Vantagens:**
- Escrita extremamente rápida (append-only em SSTables)
- Sem ponto único de falha — qualquer nó pode receber requisições
- Escalabilidade linear — adicionar nós aumenta a capacidade proporcionalmente
- Suporte nativo a coleções (list, map, set) e tipos definidos pelo usuário (UDT)

**Limitações:**
- Não possui JOINs — exige desnormalização dos dados
- Sem transações ACID entre múltiplas partições
- `GROUP BY` restrito às colunas da chave primária
- Modelo de dados deve ser projetado com base nas queries (não nas entidades)

### Ferramentas e Ecossistema

| Categoria | Ferramenta |
|---|---|
| Interface de linha de comando | `cqlsh` (nativo) |
| Interface gráfica | DBeaver (via driver JDBC) |
| Driver Python | `cassandra-driver` (DataStax) |
| Driver Java | DataStax Java Driver |
| Cloud | DataStax Astra DB (Cassandra gerenciado) |
| On-premise | Docker, instalação local |
| Monitoramento | Cassandra JMX, DataStax OpsCenter |

---

## Decisões Técnicas

### Por que Cassandra?

Cassandra foi escolhido por ser o banco NoSQL ideal para dados de estoque com alta taxa de escrita (movimentações), necessidade de leitura por múltiplos padrões de acesso (por produto, por armazém) e escalabilidade horizontal sem ponto único de falha.

### Query-First Design

Diferentemente de bancos relacionais, Cassandra exige que o schema seja projetado em função das **queries que serão executadas**, não das entidades. Por isso:

- `movimentacoes_por_produto` e `movimentacoes_por_armazem` são a mesma informação física em duas tabelas — cada uma serve um padrão de leitura eficiente.
- `estoque_por_armazem` e `estoque_por_produto` permitem busca rápida nos dois sentidos sem ALLOW FILTERING.

### UDT — User Defined Type

O tipo `frozen<endereco>` foi usado em `fornecedores` e `armazens` para demonstrar subdocumentos embutidos — equivalente ao documento aninhado do MongoDB. O `frozen` serializa o UDT como blob único; atualizações reescrevem o campo inteiro.

### LIST e MAP

- `fornecedores.telefones list<text>` — múltiplos telefones por fornecedor sem tabela auxiliar.
- `produtos.atributos map<text, text>` — atributos dinâmicos por produto (cor, peso, voltagem) sem colunas fixas no schema.

### Desnormalização Intencional

Campos como `produto_nome`, `sku` e `fornecedor_nome` são repetidos em todas as tabelas que precisam deles. Em Cassandra, JOINs não existem — a desnormalização é a estratégia correta, com o custo de manter consistência na camada de aplicação.

### Chaves de Clustering ORDER BY

Movimentações usam `CLUSTERING ORDER BY (criado_em DESC)`, garantindo que as consultas retornem sempre do mais recente para o mais antigo sem ordenação em runtime — os dados já são armazenados ordenados em disco (SSTable).

### BATCH Unlogged

O registro de movimentações usa `BEGIN UNLOGGED BATCH` para escrever em duas tabelas em uma única operação de rede. Unlogged é adequado aqui pois não há semântica transacional entre partições — é apenas uma otimização de round-trip, não uma garantia ACID.

### Aggregation no Cliente

Cassandra 4.1 não possui `GROUP BY` global eficiente. Agrupamentos como "total de produtos por categoria" são feitos em Python após buscar todos os registros — padrão esperado e documentado na página de Consultas CQL do sistema.

---

## Executando os .cql com cliente gráfico

O NoSQLBooster é um cliente exclusivo para MongoDB (fala MQL, não CQL) e **não se conecta ao Cassandra**. Para inspecionar o banco com interface gráfica, use o **DBeaver** (suporta Cassandra via driver JDBC):

1. Crie uma nova conexão do tipo "Apache Cassandra", host `localhost`, porta `9042`
2. Abra o arquivo `scripts/schema.cql` e execute como script SQL
3. Em seguida execute `scripts/seed.cql`
4. Use `USE estoque;` antes de qualquer query manual

Para uso via terminal, prefira sempre o `cqlsh` (já documentado nas seções anteriores), especialmente ao carregar arquivos `.cql` — execute-o **dentro do container** (via `docker cp` + `docker exec`) e não via pipe do shell do host, pois isso pode corromper caracteres acentuados (UTF-8).

---

## Parando o ambiente

```bash
docker compose down
```

Para remover os dados também:

```bash
docker compose down -v
```
