from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import queries
import uuid

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = "cassandra-estoque-2026"


def _str(val):
    return str(val) if val else ""


def _serializar(obj):
    if isinstance(obj, list):
        return [_serializar(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serializar(v) for k, v in obj.items()}
    if isinstance(obj, uuid.UUID):
        return str(obj)
    try:
        return obj.isoformat()
    except AttributeError:
        pass
    return obj


@app.route("/")
def index():
    kpis = queries.consulta_dashboard_kpis()
    movs = _serializar(queries.listar_todas_movimentacoes(10))
    return render_template("index.html", kpis=kpis, movimentacoes_recentes=movs)


@app.route("/produtos")
def produtos():
    lista = _serializar(queries.listar_produtos())
    categorias = _serializar(queries.listar_categorias())
    fornecedores = _serializar(queries.listar_fornecedores())
    return render_template("produtos.html",
                           produtos=lista,
                           categorias=categorias,
                           fornecedores=fornecedores)


@app.route("/produtos/novo", methods=["POST"])
def produto_criar():
    dados = {
        "nome":           request.form.get("nome", ""),
        "descricao":      request.form.get("descricao", ""),
        "sku":            request.form.get("sku", ""),
        "categoria_id":   request.form.get("categoria_id"),
        "categoria_nome": request.form.get("categoria_nome", ""),
        "fornecedor_id":  request.form.get("fornecedor_id"),
        "fornecedor_nome":request.form.get("fornecedor_nome", ""),
        "preco":          request.form.get("preco", 0),
        "unidade":        request.form.get("unidade", "un"),
        "atributos":      {},
        "tags":           [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()],
    }
    chaves   = request.form.getlist("atrib_chave")
    valores  = request.form.getlist("atrib_valor")
    dados["atributos"] = {k: v for k, v in zip(chaves, valores) if k}

    pid = queries.inserir_produto(dados)
    flash(f"Produto criado com sucesso. ID: {pid}", "success")
    return redirect(url_for("produtos"))


@app.route("/produtos/<produto_id>/editar", methods=["POST"])
def produto_editar(produto_id):
    campos = {}
    for col in ("nome", "descricao", "preco", "unidade", "categoria_nome", "fornecedor_nome"):
        val = request.form.get(col)
        if val is not None:
            campos[col] = val
    tags_raw = request.form.get("tags", "")
    if tags_raw is not None:
        campos["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
    queries.atualizar_produto(produto_id, campos)
    flash("Produto atualizado.", "success")
    return redirect(url_for("produtos"))


@app.route("/produtos/<produto_id>/excluir", methods=["POST"])
def produto_excluir(produto_id):
    queries.deletar_produto(produto_id)
    flash("Produto removido.", "success")
    return redirect(url_for("produtos"))


@app.route("/api/produtos/<produto_id>")
def api_produto(produto_id):
    p = queries.buscar_produto(produto_id)
    return jsonify(_serializar(p))


@app.route("/movimentacoes")
def movimentacoes():
    todas = _serializar(queries.listar_todas_movimentacoes(100))
    produtos = _serializar(queries.listar_produtos())
    armazens = _serializar(queries.listar_armazens())
    fornecedores = _serializar(queries.listar_fornecedores())
    return render_template("movimentacoes.html",
                           movimentacoes=todas,
                           produtos=produtos,
                           armazens=armazens,
                           fornecedores=fornecedores)


@app.route("/movimentacoes/nova", methods=["POST"])
def movimentacao_criar():
    dados = {
        "produto_id":     request.form.get("produto_id"),
        "armazem_id":     request.form.get("armazem_id"),
        "tipo":           request.form.get("tipo", "ENTRADA"),
        "quantidade":     request.form.get("quantidade", 1),
        "fornecedor_id":  request.form.get("fornecedor_id") or None,
        "fornecedor_nome":request.form.get("fornecedor_nome", ""),
        "responsavel":    request.form.get("responsavel", ""),
        "observacao":     request.form.get("observacao", ""),
    }
    mid = queries.registrar_movimentacao(dados)
    flash(f"Movimentação registrada. ID: {mid}", "success")
    return redirect(url_for("movimentacoes"))


@app.route("/movimentacoes/<produto_id>/<criado_em>/<movimentacao_id>/estornar", methods=["POST"])
def movimentacao_estornar(produto_id, criado_em, movimentacao_id):
    queries.deletar_movimentacao(produto_id, criado_em, movimentacao_id)
    flash("Movimentação estornada.", "success")
    return redirect(url_for("movimentacoes"))


@app.route("/fornecedores")
def fornecedores():
    lista = _serializar(queries.listar_fornecedores())
    return render_template("fornecedores.html", fornecedores=lista)


@app.route("/fornecedores/novo", methods=["POST"])
def fornecedor_criar():
    dados = {
        "nome":      request.form.get("nome", ""),
        "cnpj":      request.form.get("cnpj", ""),
        "email":     request.form.get("email", ""),
        "site":      request.form.get("site", ""),
        "telefones": [t.strip() for t in request.form.get("telefones", "").split(",") if t.strip()],
        "endereco": {
            "logradouro":  request.form.get("logradouro", ""),
            "numero":      request.form.get("numero", ""),
            "complemento": request.form.get("complemento", ""),
            "bairro":      request.form.get("bairro", ""),
            "cidade":      request.form.get("cidade", ""),
            "estado":      request.form.get("estado", ""),
            "cep":         request.form.get("cep", ""),
        },
    }
    fid = queries.inserir_fornecedor(dados)
    flash(f"Fornecedor cadastrado. ID: {fid}", "success")
    return redirect(url_for("fornecedores"))


@app.route("/fornecedores/<fornecedor_id>/editar", methods=["POST"])
def fornecedor_editar(fornecedor_id):
    campos = {}
    for col in ("nome", "cnpj", "email", "site"):
        val = request.form.get(col)
        if val is not None:
            campos[col] = val
    queries.atualizar_fornecedor(fornecedor_id, campos)
    flash("Fornecedor atualizado.", "success")
    return redirect(url_for("fornecedores"))


@app.route("/fornecedores/<fornecedor_id>/excluir", methods=["POST"])
def fornecedor_excluir(fornecedor_id):
    queries.deletar_fornecedor(fornecedor_id)
    flash("Fornecedor removido.", "success")
    return redirect(url_for("fornecedores"))


@app.route("/consultas")
def consultas():
    por_categoria   = _serializar(queries.consulta_contagem_por_categoria())
    estoque_critico = _serializar(queries.consulta_estoque_critico_por_armazem())
    kpis            = queries.consulta_dashboard_kpis()

    produtos = _serializar(queries.listar_produtos())
    mov_historico = []
    atributos_expandidos = None
    if produtos:
        pid = produtos[0]["produto_id"]
        mov_historico = _serializar(queries.consulta_movimentacoes_por_tipo_e_periodo(pid))
        atributos_expandidos = _serializar(queries.consulta_atributos_produto(pid))

    fornecedores = _serializar(queries.listar_fornecedores())
    armazens     = _serializar(queries.listar_armazens())

    return render_template("consultas.html",
                           por_categoria=por_categoria,
                           estoque_critico=estoque_critico,
                           kpis=kpis,
                           mov_historico=mov_historico,
                           atributos_expandidos=atributos_expandidos,
                           produtos=produtos,
                           fornecedores=fornecedores,
                           armazens=armazens)


@app.route("/api/consultas/movimentacoes/<produto_id>")
def api_mov_produto(produto_id):
    tipo = request.args.get("tipo")
    data = _serializar(queries.consulta_movimentacoes_por_tipo_e_periodo(produto_id, tipo))
    return jsonify(data)


@app.route("/api/consultas/atributos/<produto_id>")
def api_atributos(produto_id):
    data = _serializar(queries.consulta_atributos_produto(produto_id))
    return jsonify(data)


@app.route("/estoque/<armazem_id>")
def estoque_armazem(armazem_id):
    arm  = _serializar(queries.buscar_armazem(armazem_id))
    itens = _serializar(queries.listar_estoque_armazem(armazem_id))
    return jsonify({"armazem": arm, "itens": itens})


@app.route("/estoque/<armazem_id>/<produto_id>/atualizar", methods=["POST"])
def estoque_atualizar(armazem_id, produto_id):
    nova_qtd = int(request.form.get("quantidade", 0))
    status = queries.atualizar_quantidade_estoque(armazem_id, produto_id, nova_qtd)
    flash(f"Estoque atualizado. Novo status: {status}", "success")
    return redirect(url_for("produtos"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
