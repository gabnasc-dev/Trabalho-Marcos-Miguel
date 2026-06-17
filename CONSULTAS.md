# Consultas CQL — Sistema de Gestão de Estoque

---

## 1. CRUD

### Categorias

```cql
USE estoque;

-- Create
INSERT INTO categorias (categoria_id, nome, descricao, icone, criado_em)
VALUES (33333333-3333-3333-3333-333333333333, 'Eletrônicos', 'Produtos eletrônicos em geral', '💻', toTimestamp(now()));

-- Read (todos)
SELECT * FROM categorias;

-- Read (por id)
SELECT * FROM categorias WHERE categoria_id = 33333333-3333-3333-3333-333333333333;
```

> **Obs:** Update e Delete não foram implementados para categorias pois são dados de referência — alterá-las ou removê-las quebraria todos os produtos vinculados, já que o Cassandra não possui chave estrangeira para fazer essa verificação automaticamente.

---

### Fornecedores

```cql
USE estoque;

-- Create  (telefones = list<text>, endereco = UDT frozen<endereco>)
INSERT INTO fornecedores
    (fornecedor_id, nome, cnpj, email, site, telefones, endereco, ativo, criado_em)
VALUES (
    11111111-1111-1111-1111-111111111111,
    'Fornecedor Teste',
    '12.345.678/0001-99',
    'contato@fornecedorteste.com',
    'www.fornecedorteste.com.br',
    ['(11) 99999-0000', '(11) 3333-0001'],
    { logradouro: 'Rua das Flores', numero: '100', bairro: 'Centro',
      cidade: 'São Paulo', estado: 'SP', cep: '01000-000' },
    true,
    toTimestamp(now())
);

-- Read (todos)
SELECT fornecedor_id, nome, cnpj, email, site, telefones, endereco, ativo, criado_em
FROM fornecedores;

-- Read (por id)
SELECT * FROM fornecedores WHERE fornecedor_id = 11111111-1111-1111-1111-111111111111;

-- Update
UPDATE fornecedores
SET nome = 'Fornecedor Atualizado', cnpj = '98.765.432/0001-11',
    email = 'novo@fornecedorteste.com', site = 'www.novo.com.br', ativo = true
WHERE fornecedor_id = 11111111-1111-1111-1111-111111111111;

-- Delete
DELETE FROM fornecedores WHERE fornecedor_id = 11111111-1111-1111-1111-111111111111;
```

---

### Produtos

```cql
USE estoque;

-- Create  (atributos = map<text,text>, tags = list<text>)
INSERT INTO produtos
    (produto_id, nome, descricao, sku, categoria_id, categoria_nome,
     fornecedor_id, fornecedor_nome, preco, unidade, atributos, tags,
     criado_em, atualizado_em)
VALUES (
    22222222-2222-2222-2222-222222222222,
    'Notebook Dell Inspiron',
    'Notebook para uso geral e trabalho',
    'NBK-DELL-001',
    33333333-3333-3333-3333-333333333333,
    'Eletrônicos',
    11111111-1111-1111-1111-111111111111,
    'Fornecedor Teste',
    3599.90,
    'unidade',
    {'cor': 'prata', 'peso': '1.5kg', 'voltagem': 'bivolt'},
    ['eletrônico', 'notebook', 'informática'],
    toTimestamp(now()),
    toTimestamp(now())
);

-- Read (todos)
SELECT produto_id, nome, sku, categoria_nome, fornecedor_nome,
       preco, unidade, atributos, tags
FROM produtos;

-- Read (por id)
SELECT * FROM produtos WHERE produto_id = 22222222-2222-2222-2222-222222222222;

-- Read (por categoria — índice secundário)
SELECT produto_id, nome, sku, categoria_nome, preco, unidade
FROM produtos WHERE categoria_id = 33333333-3333-3333-3333-333333333333;

-- Update
UPDATE produtos
SET nome = 'Notebook Dell Inspiron 15', descricao = 'Versão atualizada',
    sku = 'NBK-DELL-001', preco = 3299.90, unidade = 'unidade',
    categoria_nome = 'Eletrônicos', fornecedor_nome = 'Fornecedor Teste',
    atributos = {'cor': 'prata', 'peso': '1.5kg', 'voltagem': 'bivolt'},
    tags = ['eletrônico', 'notebook', 'informática'],
    atualizado_em = toTimestamp(now())
WHERE produto_id = 22222222-2222-2222-2222-222222222222;

-- Delete (+ limpeza manual de estoque, pois Cassandra não tem FK/cascade)
DELETE FROM produtos WHERE produto_id = 22222222-2222-2222-2222-222222222222;
DELETE FROM estoque_por_armazem WHERE armazem_id = 44444444-4444-4444-4444-444444444444 AND produto_id = 22222222-2222-2222-2222-222222222222;
DELETE FROM estoque_por_produto  WHERE produto_id = 22222222-2222-2222-2222-222222222222 AND armazem_id = 44444444-4444-4444-4444-444444444444;
```

---

### Movimentações

```cql
USE estoque;

-- Create — escrita dupla em batch
BEGIN UNLOGGED BATCH
    INSERT INTO movimentacoes_por_produto
        (produto_id, criado_em, movimentacao_id, armazem_id, armazem_nome,
         produto_nome, sku, tipo, quantidade, quantidade_anterior,
         quantidade_posterior, fornecedor_id, fornecedor_nome, responsavel, observacao)
    VALUES (
        22222222-2222-2222-2222-222222222222,
        toTimestamp(now()),
        55555555-5555-5555-5555-555555555555,
        44444444-4444-4444-4444-444444444444,
        'Armazém Central',
        'Notebook Dell Inspiron',
        'NBK-DELL-001',
        'ENTRADA',
        10,
        0,
        10,
        11111111-1111-1111-1111-111111111111,
        'Fornecedor Teste',
        'João Silva',
        'Primeira entrada em estoque'
    );

    INSERT INTO movimentacoes_por_armazem
        (armazem_id, criado_em, movimentacao_id, produto_id, produto_nome,
         sku, tipo, quantidade, responsavel, observacao)
    VALUES (
        44444444-4444-4444-4444-444444444444,
        toTimestamp(now()),
        55555555-5555-5555-5555-555555555555,
        22222222-2222-2222-2222-222222222222,
        'Notebook Dell Inspiron',
        'NBK-DELL-001',
        'ENTRADA',
        10,
        'João Silva',
        'Primeira entrada em estoque'
    );
APPLY BATCH;

-- Read (histórico por produto, do mais recente)
SELECT * FROM movimentacoes_por_produto
WHERE produto_id = 22222222-2222-2222-2222-222222222222 LIMIT 50;

-- Read (histórico por armazém)
SELECT * FROM movimentacoes_por_armazem
WHERE armazem_id = 44444444-4444-4444-4444-444444444444 LIMIT 50;

-- Delete (estorno)
DELETE FROM movimentacoes_por_produto
WHERE produto_id = 22222222-2222-2222-2222-222222222222
  AND criado_em = '2025-06-17 10:00:00+0000'
  AND movimentacao_id = 55555555-5555-5555-5555-555555555555;
```

---

## 2. Operações Obrigatórias — Equivalentes em CQL

### aggregate

Cassandra não possui pipeline de agregação nativo como o MongoDB. A agregação é feita combinando múltiplas queries CQL simples e processando os resultados em Python.

```cql
USE estoque;

-- Agrega quantidade total e valor de estoque por armazém
SELECT quantidade, status, preco_unitario FROM estoque_por_armazem WHERE armazem_id = 22222222-2222-2222-2222-222222222201;
```

```python
# Equivalente ao aggregate pipeline — soma feita em Python
total_itens  = 0
valor_total  = 0.0
for row in rows:
    total_itens += row.quantidade or 0
    valor_total += float(row.preco_unitario or 0) * float(row.quantidade or 0)
```

Equivalente MongoDB:
```javascript
db.estoque.aggregate([
  { $match: { armazem_id: ObjectId("...") } },
  { $group: { _id: null,
              total_itens: { $sum: "$quantidade" },
              valor_total: { $sum: { $multiply: ["$quantidade", "$preco_unitario"] } } } }
])
```

---

### find

`SELECT` com filtro por chave primária. Equivale a `db.collection.find({ campo: valor })`.

```cql
USE estoque;

SELECT * FROM produtos WHERE produto_id = 22222222-2222-2222-2222-222222222222;
SELECT * FROM estoque_por_armazem WHERE armazem_id = 44444444-4444-4444-4444-444444444444;
SELECT * FROM movimentacoes_por_produto
WHERE produto_id = 22222222-2222-2222-2222-222222222222 LIMIT 50;
```

---

### $match

Cláusula `WHERE` filtrando por partition key, clustering key ou índice secundário.

```cql
USE estoque;

-- Por categoria (índice secundário)
SELECT produto_id, nome, sku, preco FROM produtos
WHERE categoria_id = 33333333-3333-3333-3333-333333333333;

-- Por tipo de movimentação
SELECT * FROM movimentacoes_por_produto
WHERE produto_id = 22222222-2222-2222-2222-222222222222
  AND tipo = 'ENTRADA' ALLOW FILTERING;
```

---

### $project

Lista explícita de colunas no `SELECT` — retorna apenas os campos necessários.

```cql
USE estoque;

SELECT produto_id, nome, sku, categoria_nome, preco, unidade
FROM produtos WHERE categoria_id = 33333333-3333-3333-3333-333333333333;

SELECT armazem_id, produto_nome, sku, quantidade, status
FROM estoque_por_armazem WHERE armazem_id = 44444444-4444-4444-4444-444444444444;
```

---

### $lookup (equivalente — desnormalização)

Cassandra não possui JOIN. O equivalente é a **desnormalização**: campos como `produto_nome`, `fornecedor_nome` e `armazem_nome` são gravados diretamente nas tabelas que precisam deles, eliminando a necessidade de junção na leitura.

```cql
USE estoque;

-- Uma única leitura já traz nome do produto e do armazém — sem JOIN
SELECT produto_nome, sku, armazem_nome, quantidade, status
FROM estoque_por_armazem;
```

Equivalente MongoDB que o Cassandra substitui por desnormalização:
```javascript
db.estoque.aggregate([
  { $match: { armazem_id: ObjectId("44444444...") } },
  { $lookup: { from: "produtos", localField: "produto_id",
               foreignField: "_id", as: "produto" } }
])
```

---

### $unwind (manipulação de arrays)

Cassandra retorna `list<text>` e `map<text,text>` nativamente como coleções. A expansão item a item (equivalente a `$unwind`) é feita em Python após a leitura.

```cql
USE estoque;

-- Leitura do array de telefones de todos os fornecedores
SELECT nome, telefones FROM fornecedores;

-- Leitura das tags e atributos de todos os produtos
SELECT nome, tags, atributos FROM produtos;
```

```python
# Expansão em Python (equivalente a $unwind)
for telefone in fornecedor["telefones"]:
    print(telefone)

for tag in produto["tags"]:
    print(tag)
```

---

### $group

CQL possui `GROUP BY` nativo, mas apenas por colunas que compõem o prefixo da chave primária. Agrupamento por `categoria_nome` (que não é chave) é feito em Python.

**Nativo (válido em CQL):**
```cql
USE estoque;

-- Contagem total de produtos
SELECT COUNT(*) FROM produtos;

-- Contagem de itens por armazém (armazem_id é partition key)
SELECT armazem_id, COUNT(*) FROM estoque_por_armazem GROUP BY armazem_id;
```

**Não nativo — feito em Python** (equivalente a `$group` por campo não-chave):
```python
# Agrupa produtos por categoria_nome
grupos = {}
for p in listar_produtos():
    cat = p.get("categoria_nome") or "Sem categoria"
    grupos.setdefault(cat, {"total": 0, "valor_total": 0.0})
    grupos[cat]["total"] += 1
    grupos[cat]["valor_total"] += float(p.get("preco") or 0)
```

Equivalente MongoDB:
```javascript
db.produtos.aggregate([
  { $group: { _id: "$categoria_nome",
              total: { $sum: 1 },
              valor_total: { $sum: "$preco" } } }
])
```

---

### Arrays

Cassandra suporta `list<text>` e `map<text,text>` nativamente.

```cql
USE estoque;

-- Inserir com array de telefones
INSERT INTO fornecedores (fornecedor_id, nome, telefones, ativo, criado_em)
VALUES (uuid(), 'Fornecedor Exemplo',
        ['(11) 99999-0000', '(11) 3333-0001'], true, toTimestamp(now()));

-- Inserir com map de atributos e list de tags
INSERT INTO produtos (produto_id, nome, atributos, tags, criado_em, atualizado_em)
VALUES (uuid(), 'Notebook Exemplo',
        {'cor': 'prata', 'peso': '1.5kg', 'voltagem': 'bivolt'},
        ['eletrônico', 'notebook', 'informática'],
        toTimestamp(now()), toTimestamp(now()));

-- Consultar
SELECT nome, telefones FROM fornecedores;
SELECT nome, atributos, tags FROM produtos;
```

---

### Subdocumentos

Cassandra usa **UDT (User Defined Type)** para subdocumentos aninhados e **MAP** para subdocumentos chave-valor dinâmicos.

**UDT `frozen<endereco>`** — análogo a subdocumento embutido:
```cql
USE estoque;

-- Definição no schema
CREATE TYPE IF NOT EXISTS estoque.endereco (
    logradouro text,
    numero     text,
    bairro     text,
    cidade     text,
    estado     text,
    cep        text
);

-- Inserção com subdocumento
INSERT INTO armazens (armazem_id, nome, endereco, criado_em)
VALUES (
    44444444-4444-4444-4444-444444444444,
    'Armazém Central',
    { logradouro: 'Rua das Flores', numero: '100', bairro: 'Centro',
      cidade: 'São Paulo', estado: 'SP', cep: '01000-000' },
    toTimestamp(now())
);

-- Leitura do subdocumento
SELECT nome, endereco FROM armazens;
SELECT nome, endereco FROM fornecedores;
```

**MAP `map<text,text>`** — subdocumento chave-valor dinâmico:
```cql
USE estoque;

-- Leitura de atributos dinâmicos de todos os produtos
SELECT nome, atributos FROM produtos;
```

---

## 3. Consultas Complexas

### Histórico de movimentações filtrado por tipo

Busca todas as saídas de um produto específico, mostrando quantidade antes e depois da movimentação.

```cql
USE estoque;

SELECT produto_nome, tipo, quantidade, quantidade_anterior, quantidade_posterior, responsavel, criado_em
FROM movimentacoes_por_produto
WHERE produto_id = 44444444-4444-4444-4444-444444444406
AND tipo = 'SAIDA' ALLOW FILTERING;
```

---

### Estoque crítico por armazém

Filtra apenas os produtos em situação crítica dentro de um armazém específico.

```cql
USE estoque;

SELECT produto_nome, sku, quantidade, status
FROM estoque_por_armazem
WHERE armazem_id = 22222222-2222-2222-2222-222222222201
AND status = 'CRITICO' ALLOW FILTERING;
```

---

### Simulação de JOIN entre duas tabelas (equivalente ao $lookup)

Cassandra não possui JOIN nativo. O equivalente é criar uma tabela desnormalizada que já une os dados das duas entidades, permitindo consulta direta sem junção em runtime.

```cql
USE estoque;

-- Criar tabela que simula o JOIN entre estoque e armazém
CREATE TABLE IF NOT EXISTS estoque_com_armazem (
    armazem_nome text,
    produto_nome text,
    produto_id   uuid,
    sku          text,
    quantidade   int,
    status       text,
    PRIMARY KEY (armazem_nome, produto_nome)
);

-- Inserir dados combinando as duas tabelas
INSERT INTO estoque_com_armazem (armazem_nome, produto_nome, produto_id, sku, quantidade, status)
VALUES ('Armazém Central', 'Teclado Mecânico Logitech MX', 44444444-4444-4444-4444-444444444401, 'TC-LOG-MX-MECH', 3, 'CRITICO');

INSERT INTO estoque_com_armazem (armazem_nome, produto_nome, produto_id, sku, quantidade, status)
VALUES ('Armazém Central', 'Notebook Dell Inspiron', 44444444-4444-4444-4444-444444444402, 'NBK-DELL-001', 15, 'EM_ESTOQUE');

INSERT INTO estoque_com_armazem (armazem_nome, produto_nome, produto_id, sku, quantidade, status)
VALUES ('Armazém Norte', 'Ar-Condicionado Split 12000', 44444444-4444-4444-4444-444444444403, 'AR-SPL-12K', 5, 'EM_ESTOQUE');

-- Consultar simulando o JOIN — retorna todos os itens de um armazém com seus dados combinados
SELECT * FROM estoque_com_armazem WHERE armazem_nome = 'Armazém Central';
```

Equivalente MongoDB:
```javascript
db.estoque.aggregate([
  { $match: { armazem_nome: "Armazém Central" } },
  { $lookup: { from: "armazens", localField: "armazem_id",
               foreignField: "_id", as: "armazem" } }
])
