"""
Todas as queries CQL do sistema com explicação do conceito NoSQL
e equivalente em MongoDB/MQL.
"""
from cassandra.query import SimpleStatement
from cassandra_client import get_session
import uuid
from datetime import datetime, timezone


def _rows_to_dicts(rows):
    return [dict(row._asdict()) for row in rows]


def _uuid(val):
    if isinstance(val, uuid.UUID):
        return val
    return uuid.UUID(str(val))


def listar_categorias():
    """
    SELECT simples sem filtro.
    Conceito: varredura completa da tabela (full partition scan).
    MongoDB equiv: db.categorias.find({})
    """
    session = get_session()
    rows = session.execute("SELECT * FROM categorias")
    return _rows_to_dicts(rows)


def buscar_categoria(categoria_id):
    """
    SELECT com filtro WHERE na chave primária.
    Conceito: lookup por chave de partição — acesso direto O(1).
    MongoDB equiv: db.categorias.findOne({ _id: ObjectId("...") })
    """
    session = get_session()
    stmt = session.prepare("SELECT * FROM categorias WHERE categoria_id = ?")
    rows = session.execute(stmt, [_uuid(categoria_id)])
    result = list(rows)
    return dict(result[0]._asdict()) if result else None


def inserir_categoria(nome, descricao, icone="tag"):
    """
    INSERT — criação de novo documento.
    MongoDB equiv: db.categorias.insertOne({ nome, descricao, icone })
    """
    session = get_session()
    stmt = session.prepare("""
        INSERT INTO categorias (categoria_id, nome, descricao, icone, criado_em)
        VALUES (?, ?, ?, ?, ?)
    """)
    cid = uuid.uuid4()
    session.execute(stmt, [cid, nome, descricao, icone, datetime.now(timezone.utc)])
    return str(cid)


def listar_fornecedores():
    """
    SELECT com UDT e LIST — retorna campos complexos.
    Conceito: subdocumento (UDT frozen<endereco>) + array (list<text>).
    MongoDB equiv: db.fornecedores.find({}, { nome:1, telefones:1, endereco:1 })
    O driver Python deserializa o UDT como namedtuple e a list como list Python.
    """
    session = get_session()
    rows = session.execute(
        "SELECT fornecedor_id, nome, cnpj, email, site, telefones, endereco, ativo, criado_em "
        "FROM fornecedores"
    )
    result = []
    for row in rows:
        d = dict(row._asdict())
        if d.get("endereco"):
            d["endereco"] = dict(d["endereco"]._asdict())
        result.append(d)
    return result


def buscar_fornecedor(fornecedor_id):
    """
    SELECT com WHERE na partition key — lookup direto.
    MongoDB equiv: db.fornecedores.findOne({ _id: ObjectId("...") })
    """
    session = get_session()
    stmt = session.prepare("SELECT * FROM fornecedores WHERE fornecedor_id = ?")
    rows = list(session.execute(stmt, [_uuid(fornecedor_id)]))
    if not rows:
        return None
    d = dict(rows[0]._asdict())
    if d.get("endereco"):
        d["endereco"] = dict(d["endereco"]._asdict())
    return d


def inserir_fornecedor(dados):
    """
    INSERT com UDT e LIST.
    Conceito: inserção de subdocumento e array numa única operação atômica.
    MongoDB equiv: db.fornecedores.insertOne({ nome, telefones: [...], endereco: {...} })
    No Cassandra, o UDT é passado como dicionário e a list como lista Python.
    """
    session = get_session()
    stmt = session.prepare("""
        INSERT INTO fornecedores
            (fornecedor_id, nome, cnpj, email, site, telefones, endereco, ativo, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """)
    fid = uuid.uuid4()
    from cassandra.util import OrderedMapSerializedKey
    endereco = dados.get("endereco", {})
    session.execute(stmt, [
        fid,
        dados["nome"],
        dados.get("cnpj", ""),
        dados.get("email", ""),
        dados.get("site", ""),
        dados.get("telefones", []),
        endereco,
        True,
        datetime.now(timezone.utc),
    ])
    return str(fid)


def atualizar_fornecedor(fornecedor_id, campos):
    """
    UPDATE seletivo de colunas escalares.
    Conceito: mutação parcial — apenas os campos enviados são reescritos.
    MongoDB equiv: db.fornecedores.updateOne({ _id }, { $set: { nome, email } })
    Cassandra não tem $set explícito: UPDATE sempre faz upsert nos campos listados.
    """
    session = get_session()
    set_parts = []
    values = []
    for col in ("nome", "cnpj", "email", "site", "ativo"):
        if col in campos:
            set_parts.append(f"{col} = ?")
            values.append(campos[col])
    if not set_parts:
        return False
    values.append(_uuid(fornecedor_id))
    cql = f"UPDATE fornecedores SET {', '.join(set_parts)} WHERE fornecedor_id = ?"
    session.execute(session.prepare(cql), values)
    return True


def deletar_fornecedor(fornecedor_id):
    """
    DELETE por chave primária.
    MongoDB equiv: db.fornecedores.deleteOne({ _id: ObjectId("...") })
    No Cassandra, DELETE sem TTL é um "tombstone" — o dado some no próximo compaction.
    """
    session = get_session()
    stmt = session.prepare("DELETE FROM fornecedores WHERE fornecedor_id = ?")
    session.execute(stmt, [_uuid(fornecedor_id)])
    return True


def listar_produtos():
    """
    SELECT com MAP e LIST.
    Conceito: projeção de coleções — equivalente a $project com arrays e maps.
    MongoDB equiv:
      db.produtos.find({}, { nome:1, atributos:1, tags:1, preco:1 })
    O driver Python entrega map<text,text> como dict e list<text> como list.
    """
    session = get_session()
    rows = session.execute(
        "SELECT produto_id, nome, descricao, sku, categoria_nome, fornecedor_nome, "
        "preco, unidade, atributos, tags, criado_em, atualizado_em FROM produtos"
    )
    result = []
    for row in rows:
        d = dict(row._asdict())
        d["atributos"] = dict(d["atributos"]) if d.get("atributos") else {}
        d["tags"] = list(d["tags"]) if d.get("tags") else []
        result.append(d)
    return result


def buscar_produto(produto_id):
    """
    SELECT por chave de partição — acesso direto.
    MongoDB equiv: db.produtos.findOne({ _id: ObjectId("...") })
    """
    session = get_session()
    stmt = session.prepare("SELECT * FROM produtos WHERE produto_id = ?")
    rows = list(session.execute(stmt, [_uuid(produto_id)]))
    if not rows:
        return None
    d = dict(rows[0]._asdict())
    d["atributos"] = dict(d["atributos"]) if d.get("atributos") else {}
    d["tags"] = list(d["tags"]) if d.get("tags") else []
    return d


def buscar_produtos_por_categoria(categoria_id):
    """
    SELECT com índice secundário.
    Conceito: filtro em coluna não-chave via índice (ALLOW FILTERING implícito
    quando há índice). Uso moderado — índices secundários em Cassandra têm custo.
    MongoDB equiv: db.produtos.find({ categoria_id: ObjectId("...") })
    (equivalente a índice simples em MongoDB)
    """
    session = get_session()
    stmt = session.prepare(
        "SELECT produto_id, nome, sku, categoria_nome, preco, unidade "
        "FROM produtos WHERE categoria_id = ?"
    )
    rows = session.execute(stmt, [_uuid(categoria_id)])
    return _rows_to_dicts(rows)


def inserir_produto(dados):
    """
    INSERT com MAP e LIST.
    Conceito: inserção de coleções heterogêneas num único documento.
    MongoDB equiv:
      db.produtos.insertOne({ nome, atributos: { "cor":"azul" }, tags: ["fragil"] })
    """
    session = get_session()
    stmt = session.prepare("""
        INSERT INTO produtos
            (produto_id, nome, descricao, sku, categoria_id, categoria_nome,
             fornecedor_id, fornecedor_nome, preco, unidade,
             atributos, tags, criado_em, atualizado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """)
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    session.execute(stmt, [
        pid,
        dados["nome"],
        dados.get("descricao", ""),
        dados.get("sku", ""),
        _uuid(dados["categoria_id"]) if dados.get("categoria_id") else None,
        dados.get("categoria_nome", ""),
        _uuid(dados["fornecedor_id"]) if dados.get("fornecedor_id") else None,
        dados.get("fornecedor_nome", ""),
        float(dados.get("preco", 0)),
        dados.get("unidade", "un"),
        dados.get("atributos", {}),
        dados.get("tags", []),
        now,
        now,
    ])
    return str(pid)


def atualizar_produto(produto_id, campos):
    """
    UPDATE parcial incluindo MAP e LIST.
    Conceito: mutação de coleções — Cassandra suporta operações em map/list
    individualmente (ex: atributos['cor'] = 'verde' ou tags = tags + ['novo']).
    Aqui fazemos substituição completa da coleção, similar ao $set do MongoDB.
    MongoDB equiv: db.produtos.updateOne({ _id }, { $set: { nome, atributos, tags } })
    """
    session = get_session()
    set_parts = []
    values = []
    for col in ("nome", "descricao", "sku", "preco", "unidade",
                "categoria_nome", "fornecedor_nome", "atributos", "tags"):
        if col in campos:
            set_parts.append(f"{col} = ?")
            values.append(campos[col])
    set_parts.append("atualizado_em = ?")
    values.append(datetime.now(timezone.utc))
    values.append(_uuid(produto_id))
    cql = f"UPDATE produtos SET {', '.join(set_parts)} WHERE produto_id = ?"
    session.execute(session.prepare(cql), values)
    return True


def deletar_produto(produto_id):
    """
    DELETE em cascata manual: remove da tabela de produtos e das tabelas de estoque.
    MongoDB equiv: db.produtos.deleteOne({ _id }) + db.estoque.deleteMany({ produto_id })
    Cassandra não tem transações multi-tabela; cada DELETE é independente.
    """
    session = get_session()
    pid = _uuid(produto_id)
    session.execute(
        session.prepare("DELETE FROM produtos WHERE produto_id = ?"), [pid]
    )
    linhas_estoque = session.execute(
        session.prepare("SELECT armazem_id FROM estoque_por_produto WHERE produto_id = ?"),
        [pid]
    )
    for row in linhas_estoque:
        session.execute(
            session.prepare(
                "DELETE FROM estoque_por_armazem WHERE armazem_id = ? AND produto_id = ?"
            ),
            [row.armazem_id, pid]
        )
    session.execute(
        session.prepare("DELETE FROM estoque_por_produto WHERE produto_id = ?"), [pid]
    )
    return True


def listar_armazens():
    """
    SELECT com UDT — subdocumento de endereço.
    MongoDB equiv: db.armazens.find({})
    """
    session = get_session()
    rows = session.execute("SELECT * FROM armazens")
    result = []
    for row in rows:
        d = dict(row._asdict())
        if d.get("endereco"):
            d["endereco"] = dict(d["endereco"]._asdict())
        result.append(d)
    return result


def buscar_armazem(armazem_id):
    session = get_session()
    stmt = session.prepare("SELECT * FROM armazens WHERE armazem_id = ?")
    rows = list(session.execute(stmt, [_uuid(armazem_id)]))
    if not rows:
        return None
    d = dict(rows[0]._asdict())
    if d.get("endereco"):
        d["endereco"] = dict(d["endereco"]._asdict())
    return d


def listar_estoque_armazem(armazem_id):
    """
    SELECT com chave de partição composta — busca todos os produtos de um armazém.
    Conceito: particionamento — todos os itens do armazém vivem na mesma partição,
    tornando esta query extremamente eficiente (1 nó, leitura sequencial).
    MongoDB equiv (com $lookup):
      db.estoque.aggregate([
        { $match: { armazem_id: ObjectId("...") } },
        { $lookup: { from: "produtos", localField: "produto_id", foreignField: "_id", as: "produto" } }
      ])
    No Cassandra não há $lookup: os dados já estão desnormalizados na tabela.
    """
    session = get_session()
    stmt = session.prepare(
        "SELECT * FROM estoque_por_armazem WHERE armazem_id = ?"
    )
    rows = session.execute(stmt, [_uuid(armazem_id)])
    return _rows_to_dicts(rows)


def atualizar_quantidade_estoque(armazem_id, produto_id, nova_quantidade):
    """
    UPDATE de quantidade e status recalculado.
    Conceito: mutação de campo escalar com lógica de negócio no driver.
    Em Cassandra não existe lógica condicional nativa no UPDATE (há lightweight
    transactions com IF, mas têm custo alto). A regra de status é aplicada na app.
    MongoDB equiv: db.estoque.updateOne(
        { armazem_id, produto_id },
        { $set: { quantidade, status } }
    )
    """
    session = get_session()
    row = list(session.execute(
        session.prepare(
            "SELECT quantidade_minima FROM estoque_por_armazem "
            "WHERE armazem_id = ? AND produto_id = ?"
        ),
        [_uuid(armazem_id), _uuid(produto_id)]
    ))
    qtd_min = row[0].quantidade_minima if row else 5
    if nova_quantidade == 0:
        status = "ZERADO"
    elif nova_quantidade <= qtd_min:
        status = "CRITICO"
    else:
        status = "EM_ESTOQUE"

    now = datetime.now(timezone.utc)
    stmt = session.prepare("""
        UPDATE estoque_por_armazem
        SET quantidade = ?, status = ?, atualizado_em = ?
        WHERE armazem_id = ? AND produto_id = ?
    """)
    session.execute(stmt, [nova_quantidade, status, now, _uuid(armazem_id), _uuid(produto_id)])

    stmt2 = session.prepare("""
        UPDATE estoque_por_produto
        SET quantidade = ?, status = ?, atualizado_em = ?
        WHERE produto_id = ? AND armazem_id = ?
    """)
    session.execute(stmt2, [nova_quantidade, status, now, _uuid(produto_id), _uuid(armazem_id)])
    return status


def listar_movimentacoes_produto(produto_id, limit=50):
    """
    SELECT com clustering ORDER BY — retorna as N mais recentes.
    Conceito: dados ordenados por tempo dentro da partição (clustering column).
    O Cassandra armazena os dados já ordenados em disco — não há sort em runtime.
    MongoDB equiv:
      db.movimentacoes.find({ produto_id }).sort({ criado_em: -1 }).limit(50)
    """
    session = get_session()
    stmt = session.prepare(
        "SELECT * FROM movimentacoes_por_produto "
        "WHERE produto_id = ? LIMIT ?"
    )
    rows = session.execute(stmt, [_uuid(produto_id), limit])
    return _rows_to_dicts(rows)


def listar_movimentacoes_armazem(armazem_id, limit=50):
    """
    SELECT por armazém — tabela separada para este padrão de acesso.
    Conceito: "query-first design" — o mesmo dado físico é escrito em duas tabelas
    para suportar dois padrões de leitura eficientes.
    MongoDB equiv: db.movimentacoes.find({ armazem_id }).sort({ criado_em: -1 }).limit(50)
    """
    session = get_session()
    stmt = session.prepare(
        "SELECT * FROM movimentacoes_por_armazem "
        "WHERE armazem_id = ? LIMIT ?"
    )
    rows = session.execute(stmt, [_uuid(armazem_id), limit])
    return _rows_to_dicts(rows)


def listar_todas_movimentacoes(limit=100):
    """
    SELECT em todas as partições — menos eficiente, usado apenas para dashboard.
    MongoDB equiv: db.movimentacoes.find({}).sort({ criado_em: -1 }).limit(100)
    """
    session = get_session()
    rows = session.execute(
        SimpleStatement(
            "SELECT * FROM movimentacoes_por_produto LIMIT %d" % limit,
            fetch_size=100
        )
    )
    return _rows_to_dicts(rows)


def registrar_movimentacao(dados):
    """
    INSERT duplo — desnormalização intencional para suportar dois padrões de acesso.
    Conceito: escrita duplicada (write amplification) é o custo do Cassandra para
    garantir leituras eficientes sem JOINs.
    MongoDB equiv:
      db.movimentacoes.insertOne({ produto_id, armazem_id, tipo, quantidade, ... })
    No Cassandra, escrevemos em duas tabelas atomicamente via BATCH (unlogged —
    garante que ambas as escritas chegam ao mesmo nó de coordenação).
    Unlogged BATCH é adequado pois não há semântica transacional entre partições.
    """
    session = get_session()
    mid = uuid.uuid4()
    now = datetime.now(timezone.utc)

    produto_id  = _uuid(dados["produto_id"])
    armazem_id  = _uuid(dados["armazem_id"])
    tipo        = dados["tipo"].upper()
    quantidade  = int(dados["quantidade"])
    fornecedor_id = _uuid(dados["fornecedor_id"]) if dados.get("fornecedor_id") else None

    prod = buscar_produto(str(produto_id))
    arm  = buscar_armazem(str(armazem_id))
    produto_nome = prod["nome"] if prod else dados.get("produto_nome", "")
    sku          = prod["sku"]  if prod else dados.get("sku", "")
    armazem_nome = arm["nome"] if arm else dados.get("armazem_nome", "")
    fornecedor_nome = dados.get("fornecedor_nome", "")

    est = list(session.execute(
        session.prepare(
            "SELECT quantidade FROM estoque_por_armazem WHERE armazem_id = ? AND produto_id = ?"
        ),
        [armazem_id, produto_id]
    ))
    qtd_anterior = est[0].quantidade if est else 0
    if tipo == "ENTRADA":
        qtd_posterior = qtd_anterior + quantidade
    else:
        qtd_posterior = max(0, qtd_anterior - quantidade)

    batch_cql = """
    BEGIN UNLOGGED BATCH
        INSERT INTO movimentacoes_por_produto
            (produto_id, criado_em, movimentacao_id, armazem_id, armazem_nome,
             produto_nome, sku, tipo, quantidade, quantidade_anterior,
             quantidade_posterior, fornecedor_id, fornecedor_nome, responsavel, observacao)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);

        INSERT INTO movimentacoes_por_armazem
            (armazem_id, criado_em, movimentacao_id, produto_id, produto_nome,
             sku, tipo, quantidade, responsavel, observacao)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    APPLY BATCH;
    """

    def _q(v):
        if v is None:
            return "null"
        if isinstance(v, uuid.UUID):
            return str(v)
        if isinstance(v, str):
            return "'" + v.replace("'", "''") + "'"
        if isinstance(v, datetime):
            return "'" + v.strftime("%Y-%m-%d %H:%M:%S+0000") + "'"
        return str(v)

    fornecedor_id_q = _q(fornecedor_id)
    cql = batch_cql % (
        _q(produto_id), _q(now), _q(mid), _q(armazem_id), _q(armazem_nome),
        _q(produto_nome), _q(sku), _q(tipo), quantidade, qtd_anterior,
        qtd_posterior, fornecedor_id_q, _q(fornecedor_nome),
        _q(dados.get("responsavel", "")), _q(dados.get("observacao", "")),
        _q(armazem_id), _q(now), _q(mid), _q(produto_id), _q(produto_nome),
        _q(sku), _q(tipo), quantidade,
        _q(dados.get("responsavel", "")), _q(dados.get("observacao", "")),
    )
    session.execute(cql)

    atualizar_quantidade_estoque(str(armazem_id), str(produto_id), qtd_posterior)
    return str(mid)


def deletar_movimentacao(produto_id, criado_em_str, movimentacao_id):
    """
    DELETE com clustering key — remove registro específico dentro de uma partição.
    Conceito: deleção precisa usando chave composta (partition key + clustering key).
    MongoDB equiv: db.movimentacoes.deleteOne({ produto_id, criado_em, _id })
    Nota: no Cassandra não há "rollback" automático do estoque; a lógica de
    estorno é feita manualmente na camada de aplicação.
    """
    session = get_session()
    from datetime import datetime
    if isinstance(criado_em_str, str):
        criado_em = datetime.fromisoformat(criado_em_str.replace("Z", "+00:00"))
    else:
        criado_em = criado_em_str

    stmt = session.prepare("""
        DELETE FROM movimentacoes_por_produto
        WHERE produto_id = ? AND criado_em = ? AND movimentacao_id = ?
    """)
    session.execute(stmt, [_uuid(produto_id), criado_em, _uuid(movimentacao_id)])
    return True


def consulta_contagem_por_categoria():
    """
    CONSULTA COMPLEXA 1 — Agrupamento e contagem por categoria.

    Conceito CQL: Cassandra não tem GROUP BY nativo (disponível apenas em versões
    recentes e com limitações). Fazemos o agrupamento em Python após buscar todos
    os produtos — padrão comum em Cassandra (aggregation na camada de aplicação).

    MongoDB equiv (pipeline de agregação):
      db.produtos.aggregate([
        { $group: {
            _id: "$categoria_nome",
            total_produtos: { $sum: 1 },
            valor_total: { $sum: "$preco" }
        }},
        { $sort: { total_produtos: -1 } }
      ])

    Cassandra 4.x com ALLOW FILTERING permite GROUP BY simples apenas dentro
    de uma partição. Para agrupamento global, a abordagem correta é:
    - Manter uma tabela de contadores dedicada (counter table), ou
    - Fazer a agregação no cliente (como fazemos aqui), ou
    - Usar Spark+Cassandra para analytics.
    """
    produtos = listar_produtos()
    grupos = {}
    for p in produtos:
        cat = p.get("categoria_nome") or "Sem categoria"
        if cat not in grupos:
            grupos[cat] = {"categoria": cat, "total_produtos": 0, "valor_total": 0.0}
        grupos[cat]["total_produtos"] += 1
        grupos[cat]["valor_total"] += float(p.get("preco") or 0)
    return sorted(grupos.values(), key=lambda x: x["total_produtos"], reverse=True)


def consulta_estoque_critico_por_armazem():
    """
    CONSULTA COMPLEXA 2 — Produtos em estado crítico ou zerado por armazém.

    Conceito CQL: filtro em coluna de clustering com IN.
    Cassandra suporta filtro em colunas de clustering (não de partição) com ALLOW
    FILTERING ou quando há índice. Para este caso, varremos todas as partições
    conhecidas (lista de armazéns) e filtramos status.

    MongoDB equiv:
      db.estoque.aggregate([
        { $match: { status: { $in: ["CRITICO", "ZERADO"] } } },
        { $lookup: { from: "armazens", localField: "armazem_id", foreignField: "_id", as: "armazem" } },
        { $group: { _id: "$armazem_id", armazem: { $first: "$armazem.nome" }, itens: { $push: "$$ROOT" } } }
      ])

    No Cassandra, simulamos o $lookup e o $group na aplicação.
    """
    session = get_session()
    armazens = listar_armazens()
    resultado = []
    for arm in armazens:
        stmt = session.prepare(
            "SELECT produto_nome, sku, quantidade, quantidade_minima, status, unidade "
            "FROM estoque_por_armazem WHERE armazem_id = ?"
        )
        rows = session.execute(stmt, [arm["armazem_id"]])
        criticos = [dict(r._asdict()) for r in rows if r.status in ("CRITICO", "ZERADO")]
        if criticos:
            resultado.append({
                "armazem_id":   str(arm["armazem_id"]),
                "armazem_nome": arm["nome"],
                "itens_criticos": criticos,
                "total_critico":  len(criticos),
            })
    return resultado


def consulta_movimentacoes_por_tipo_e_periodo(produto_id, tipo=None):
    """
    CONSULTA COMPLEXA 3 — Histórico de movimentações com projeção de campos.

    Conceito CQL:
    - Particionamento por produto_id: todos os dados do produto numa partição.
    - Clustering por criado_em DESC: leitura já ordenada, sem sort extra.
    - Projeção de colunas específicas: equivalente ao $project do MongoDB.
    - Filtro opcional por tipo (ENTRADA/SAIDA) via ALLOW FILTERING (aceitável
      pois o filtro é dentro de uma única partição — baixo custo).

    MongoDB equiv:
      db.movimentacoes.find(
        { produto_id: ObjectId("..."), tipo: "ENTRADA" },
        { tipo:1, quantidade:1, quantidade_anterior:1, quantidade_posterior:1,
          responsavel:1, criado_em:1 }
      ).sort({ criado_em: -1 })
    """
    session = get_session()
    if tipo:
        stmt = session.prepare("""
            SELECT tipo, quantidade, quantidade_anterior, quantidade_posterior,
                   armazem_nome, responsavel, observacao, criado_em
            FROM movimentacoes_por_produto
            WHERE produto_id = ? AND tipo = ?
            ALLOW FILTERING
        """)
        rows = session.execute(stmt, [_uuid(produto_id), tipo.upper()])
    else:
        stmt = session.prepare("""
            SELECT tipo, quantidade, quantidade_anterior, quantidade_posterior,
                   armazem_nome, responsavel, observacao, criado_em
            FROM movimentacoes_por_produto
            WHERE produto_id = ?
        """)
        rows = session.execute(stmt, [_uuid(produto_id)])
    return _rows_to_dicts(rows)


def consulta_atributos_produto(produto_id):
    """
    CONSULTA COMPLEXA 4 — Leitura e expansão de MAP (subdocumento de atributos).

    Conceito CQL: MAP<text, text> como subdocumento chave-valor.
    O MAP é armazenado como uma coleção ordenada de pares. Podemos ler
    valores individuais com atributos['chave'] ou o map inteiro.
    Equivalente ao $unwind + $project de arrays/maps em MongoDB.

    MongoDB equiv:
      db.produtos.aggregate([
        { $match: { _id: ObjectId("...") } },
        { $project: { atributos: 1, tags: 1, nome: 1 } },
        // Para expandir o map como array de pares chave-valor:
        { $addFields: {
            atributos_array: { $objectToArray: "$atributos" }
          }
        }
      ])

    No Cassandra, o driver retorna o map<text,text> como dict Python.
    Convertemos para lista de pares para exibição na interface.
    """
    produto = buscar_produto(produto_id)
    if not produto:
        return None
    atributos_expandidos = [
        {"chave": k, "valor": v}
        for k, v in (produto.get("atributos") or {}).items()
    ]
    return {
        "produto_id":   produto_id,
        "nome":         produto["nome"],
        "sku":          produto["sku"],
        "tags":         produto.get("tags", []),
        "atributos":    atributos_expandidos,
        "total_atributos": len(atributos_expandidos),
    }


def consulta_dashboard_kpis():
    """
    CONSULTA COMPLEXA 5 — KPIs do dashboard (múltiplas queries agregadas).

    Conceito: agregação multi-tabela no cliente — padrão obrigatório em Cassandra
    pois não há JOINs. Cada tabela serve um padrão de acesso; o dashboard combina
    resultados de múltiplas queries.

    MongoDB equiv:
      Promise.all([
        db.produtos.countDocuments(),
        db.estoque.aggregate([{ $group: { _id: null, total: { $sum: "$quantidade" } } }]),
        db.estoque.countDocuments({ status: { $in: ["CRITICO","ZERADO"] } }),
        db.movimentacoes.find({ tipo:"ENTRADA" }).count()
      ])
    """
    session = get_session()

    total_produtos = len(listar_produtos())
    total_fornecedores = len(listar_fornecedores())
    total_armazens = len(listar_armazens())

    armazens = listar_armazens()
    total_itens = 0
    itens_criticos = 0
    valor_estoque = 0.0
    for arm in armazens:
        rows = session.execute(
            session.prepare(
                "SELECT quantidade, status, preco_unitario FROM estoque_por_armazem WHERE armazem_id = ?"
            ),
            [arm["armazem_id"]]
        )
        for row in rows:
            total_itens += (row.quantidade or 0)
            if row.status in ("CRITICO", "ZERADO"):
                itens_criticos += 1
            valor_estoque += float(row.preco_unitario or 0) * float(row.quantidade or 0)

    movs = listar_todas_movimentacoes(200)
    entradas = sum(1 for m in movs if m.get("tipo") == "ENTRADA")
    saidas   = sum(1 for m in movs if m.get("tipo") == "SAIDA")

    return {
        "total_produtos":     total_produtos,
        "total_fornecedores": total_fornecedores,
        "total_armazens":     total_armazens,
        "total_itens_estoque": total_itens,
        "itens_criticos":     itens_criticos,
        "valor_total_estoque": round(valor_estoque, 2),
        "total_entradas":     entradas,
        "total_saidas":       saidas,
    }
