-- =============================================================================
-- SCHEMA — Sistema de Gestão de Estoque
-- Banco: Apache Cassandra 4.1
-- Trabalho Acadêmico — Banco de Dados Não Relacionais
-- =============================================================================
-- NOTA SOBRE MODELAGEM CASSANDRA:
--   Cassandra exige "query-first design": cada tabela é criada para servir
--   um padrão de acesso específico. Desnormalização intencional é esperada.
--   A chave de partição determina em qual nó o dado reside; colunas de
--   clustering definem a ordem dos dados dentro da partição.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. KEYSPACE
-- -----------------------------------------------------------------------------
CREATE KEYSPACE IF NOT EXISTS estoque
    WITH replication = {
        'class': 'SimpleStrategy',
        'replication_factor': 1
    }
    AND durable_writes = true;

USE estoque;

-- -----------------------------------------------------------------------------
-- 2. USER DEFINED TYPE (UDT) — equivalente a subdocumento no MongoDB
-- -----------------------------------------------------------------------------
-- Em MongoDB: { endereco: { logradouro: "Rua X", numero: "10", ... } }
-- No Cassandra: frozen<endereco> embute o UDT diretamente na linha da tabela.
-- "frozen" significa que o valor inteiro é serializado como um blob —
-- qualquer atualização reescreve o UDT completo.

CREATE TYPE IF NOT EXISTS estoque.endereco (
    logradouro text,
    numero     text,
    complemento text,
    bairro     text,
    cidade     text,
    estado     text,
    cep        text
);

-- -----------------------------------------------------------------------------
-- 3. TABELAS DE REFERÊNCIA (lookup tables)
-- -----------------------------------------------------------------------------

-- 3.1 Categorias
-- Padrão de acesso: buscar categoria por ID (chave primária simples)
CREATE TABLE IF NOT EXISTS estoque.categorias (
    categoria_id  uuid        PRIMARY KEY,
    nome          text,
    descricao     text,
    icone         text,
    criado_em     timestamp
);

-- 3.2 Fornecedores
-- Demonstra: UDT frozen<endereco> + LIST<text> para múltiplos telefones
-- Em MongoDB: { telefones: ["11999...", "1133..."] }  ← array simples
-- No Cassandra: list<text> é uma coleção ordenada de valores

CREATE TABLE IF NOT EXISTS estoque.fornecedores (
    fornecedor_id uuid        PRIMARY KEY,
    nome          text,
    cnpj          text,
    email         text,
    site          text,
    telefones     list<text>,              -- LIST: múltiplos contatos
    endereco      frozen<endereco>,        -- UDT: subdocumento de endereço
    ativo         boolean,
    criado_em     timestamp
);

-- 3.3 Armazéns
-- Demonstra: UDT frozen<endereco> reutilizado em outra entidade
CREATE TABLE IF NOT EXISTS estoque.armazens (
    armazem_id  uuid       PRIMARY KEY,
    nome        text,
    capacidade  int,
    responsavel text,
    endereco    frozen<endereco>,           -- UDT: mesmo tipo, entidade diferente
    ativo       boolean,
    criado_em   timestamp
);

-- -----------------------------------------------------------------------------
-- 4. PRODUTOS
-- -----------------------------------------------------------------------------
-- Demonstra: MAP<text, text> para atributos dinâmicos + LIST<text> para tags
-- Em MongoDB: { atributos: { "cor": "azul", "peso": "1kg" }, tags: ["eletrônico"] }
-- No Cassandra: map<text, text> é um dicionário chave→valor; list<text> é array

CREATE TABLE IF NOT EXISTS estoque.produtos (
    produto_id      uuid        PRIMARY KEY,
    nome            text,
    descricao       text,
    sku             text,
    categoria_id    uuid,
    categoria_nome  text,                  -- desnormalizado para evitar JOIN
    fornecedor_id   uuid,
    fornecedor_nome text,                  -- desnormalizado para evitar JOIN
    preco           decimal,
    unidade         text,                  -- ex: "un", "kg", "cx"
    atributos       map<text, text>,       -- MAP: { "cor":"azul", "peso":"500g" }
    tags            list<text>,            -- LIST: ["fragil", "refrigerado"]
    criado_em       timestamp,
    atualizado_em   timestamp
);

-- Índice secundário para busca por SKU (uso com cautela em Cassandra)
CREATE INDEX IF NOT EXISTS idx_produto_sku ON estoque.produtos (sku);

-- Índice secundário para busca por categoria
CREATE INDEX IF NOT EXISTS idx_produto_categoria ON estoque.produtos (categoria_id);

-- -----------------------------------------------------------------------------
-- 5. ESTOQUE POR ARMAZÉM
-- -----------------------------------------------------------------------------
-- Padrão de acesso: "qual é o estoque de um armazém específico?"
-- Chave de partição: armazem_id → todos os produtos do armazém ficam juntos
-- Chave de clustering: produto_id → ordena produtos dentro da partição
--
-- Em MongoDB equivaleria a uma coleção "estoque" com índice em { armazem_id, produto_id }
-- e uma pipeline de $lookup para trazer dados do produto.

CREATE TABLE IF NOT EXISTS estoque.estoque_por_armazem (
    armazem_id        uuid,
    produto_id        uuid,
    produto_nome      text,
    sku               text,
    categoria_nome    text,
    fornecedor_nome   text,
    quantidade        int,
    quantidade_minima int,
    status            text,               -- 'EM_ESTOQUE', 'CRITICO', 'ZERADO', 'EM_TRANSITO'
    unidade           text,
    preco_unitario    decimal,
    atualizado_em     timestamp,
    PRIMARY KEY (armazem_id, produto_id)
);

-- Tabela inversa: "em quais armazéns um produto específico está presente?"
-- Padrão de acesso diferente → tabela separada (query-first design)
CREATE TABLE IF NOT EXISTS estoque.estoque_por_produto (
    produto_id        uuid,
    armazem_id        uuid,
    armazem_nome      text,
    quantidade        int,
    quantidade_minima int,
    status            text,
    atualizado_em     timestamp,
    PRIMARY KEY (produto_id, armazem_id)
);

-- -----------------------------------------------------------------------------
-- 6. MOVIMENTAÇÕES
-- -----------------------------------------------------------------------------
-- Padrão de acesso primário: "quais movimentações ocorreram para um produto?"
-- Partição: produto_id | Clustering: criado_em DESC (mais recentes primeiro)
-- timeuuid garante unicidade mesmo para timestamps idênticos

CREATE TABLE IF NOT EXISTS estoque.movimentacoes_por_produto (
    produto_id      uuid,
    criado_em       timestamp,
    movimentacao_id uuid,
    armazem_id      uuid,
    armazem_nome    text,
    produto_nome    text,
    sku             text,
    tipo            text,                 -- 'ENTRADA' ou 'SAIDA'
    quantidade      int,
    quantidade_anterior int,
    quantidade_posterior int,
    fornecedor_id   uuid,
    fornecedor_nome text,
    responsavel     text,
    observacao      text,
    PRIMARY KEY (produto_id, criado_em, movimentacao_id)
) WITH CLUSTERING ORDER BY (criado_em DESC, movimentacao_id ASC);

-- Padrão de acesso alternativo: "quais movimentações ocorreram em um armazém?"
-- Exige tabela separada — Cassandra não faz "scan" eficiente em múltiplas partições
CREATE TABLE IF NOT EXISTS estoque.movimentacoes_por_armazem (
    armazem_id      uuid,
    criado_em       timestamp,
    movimentacao_id uuid,
    produto_id      uuid,
    produto_nome    text,
    sku             text,
    tipo            text,
    quantidade      int,
    responsavel     text,
    observacao      text,
    PRIMARY KEY (armazem_id, criado_em, movimentacao_id)
) WITH CLUSTERING ORDER BY (criado_em DESC, movimentacao_id ASC);

-- =============================================================================
-- FIM DO SCHEMA
-- =============================================================================
