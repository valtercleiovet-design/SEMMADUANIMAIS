from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from database import conectar, criar_tabelas
import os

app = Flask(__name__)
app.secret_key = 'segredo_super_seguro'

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

criar_tabelas()

# 🔓 HOME
@app.route('/')
def index():
    return render_template('index.html')


# 🔐 LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM usuarios WHERE usuario=? AND senha=?",
            (usuario, senha)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session['logado'] = True
            session['usuario'] = usuario
            return redirect(url_for('painel'))
        else:
            return render_template('login.html', erro="Usuário ou senha inválidos")

    return render_template('login.html')


# 🚪 LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# 🚨 DENÚNCIA
@app.route('/denunciar', methods=['GET', 'POST'])
def denunciar():
    if request.method == 'POST':
        descricao = request.form['descricao']
        tipo = request.form['tipo']
        localizacao = request.form['localizacao']

        arquivo = request.files.get('imagem')
        caminho_imagem = None

        if arquivo and arquivo.filename != '':
            caminho_imagem = os.path.join(UPLOAD_FOLDER, arquivo.filename)
            arquivo.save(caminho_imagem)

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO denuncias (tipo, descricao, localizacao, imagem, status)
            VALUES (?, ?, ?, ?, ?)
        """, (tipo, descricao, localizacao, caminho_imagem, "Recebido"))

        denuncia_id = cursor.lastrowid

        # histórico
        cursor.execute("""
            INSERT INTO historico (denuncia_id, status, observacao)
            VALUES (?, ?, ?)
        """, (denuncia_id, "Recebido", "Denúncia criada"))

        conn.commit()
        conn.close()

        return redirect(url_for('index'))

    return render_template('denunciar.html')


# 🔒 PAINEL (CORRIGIDO E COMPLETO)
@app.route('/painel')
def painel():
    if not session.get('logado'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    # 📋 lista de denúncias
    cursor.execute("SELECT * FROM denuncias ORDER BY id DESC")
    dados = cursor.fetchall()

    # 📊 contagens
    cursor.execute("SELECT COUNT(*) FROM denuncias")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE status='Recebido'")
    recebido = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE status='Em fiscalização'")
    fiscalizacao = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE status='Resolvido'")
    resolvido = cursor.fetchone()[0]

    conn.close()

    return render_template(
        'painel.html',
        dados=dados,
        total=total,
        recebido=recebido,
        fiscalizacao=fiscalizacao,
        resolvido=resolvido
    )


# 🔄 ATUALIZAR STATUS
@app.route('/atualizar_status/<int:id>/<novo_status>')
def atualizar_status(id, novo_status):
    if not session.get('logado'):
        return redirect('/login')

    novo_status = novo_status.replace("_", " ")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("UPDATE denuncias SET status=? WHERE id=?", (novo_status, id))

    cursor.execute("""
        INSERT INTO historico (denuncia_id, status, observacao)
        VALUES (?, ?, ?)
    """, (id, novo_status, "Atualizado pelo servidor"))

    conn.commit()
    conn.close()

    return redirect('/painel')


# 📍 MAPA GERAL
@app.route('/mapa')
def mapa():
    if not session.get('logado'):
        return redirect('/login')
    return render_template('mapa.html')


# 📍 MAPA INDIVIDUAL
@app.route('/mapa/<int:id>')
def mapa_unico(id):
    if not session.get('logado'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT tipo, descricao, localizacao FROM denuncias WHERE id=?", (id,))
    dado = cursor.fetchone()

    conn.close()

    return render_template('mapa_unico.html', dado=dado)


# 📡 DADOS DO MAPA
@app.route('/dados_mapa')
def dados_mapa():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT id, tipo, descricao, localizacao, status FROM denuncias")
    dados = cursor.fetchall()

    conn.close()

    lista = []
    for d in dados:
        lista.append({
            "id": d[0],
            "tipo": d[1],
            "descricao": d[2],
            "localizacao": d[3],
            "status": d[4]
        })

    return jsonify(lista)


# 📊 DASHBOARD
@app.route('/dashboard')
def dashboard():
    if not session.get('logado'):
        return redirect('/login')
    return render_template('dashboard.html')


@app.route('/dados_dashboard')
def dados_dashboard():
    conn = conectar()
    cursor = conn.cursor()

    # por tipo
    cursor.execute("SELECT tipo, COUNT(*) FROM denuncias GROUP BY tipo")
    dados_tipo = cursor.fetchall()

    # por status
    cursor.execute("SELECT status, COUNT(*) FROM denuncias GROUP BY status")
    dados_status = cursor.fetchall()

    # total
    cursor.execute("SELECT COUNT(*) FROM denuncias")
    total = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        "total": total,
        "tipos": {
            "labels": [d[0] for d in dados_tipo],
            "valores": [d[1] for d in dados_tipo]
        },
        "status": {
            "labels": [d[0] for d in dados_status],
            "valores": [d[1] for d in dados_status]
        }
    })


# 🚀 RUN
if __name__ == '__main__':
    app.run(debug=True)