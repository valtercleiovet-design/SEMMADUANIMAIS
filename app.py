from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from database import conectar, criar_tabelas
import os

app = Flask(__name__)
app.secret_key = 'segredo_super_seguro'

# 📧 CONFIG EMAIL
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'semmadubemestaranimal@gmail.com'
app.config['MAIL_PASSWORD'] = 'feqtqxnzlmurmzuo'
app.config['MAIL_DEFAULT_SENDER'] = 'semmadubemestaranimal@gmail.com'

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# 📁 UPLOAD
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 🗄️ BANCO
criar_tabelas()


# 🔓 HOME
@app.route('/')
def index():
    return render_template('index.html')


# 🔐 LOGIN (CORRIGIDO)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM usuarios WHERE email=?", (email,))
        user = cursor.fetchone()

        conn.close()

        if user and user[3] == senha:
            session['logado'] = True
            session['usuario'] = user[1]
            return redirect(url_for('painel'))
        else:
            return render_template('login.html', erro="Usuário ou senha inválidos")

    return render_template('login.html')


# 🔁 ESQUECI SENHA (CORRIGIDO)
@app.route('/esqueci_senha', methods=['GET', 'POST'])
def esqueci_senha():
    if request.method == 'POST':
        email = request.form['email']

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM usuarios WHERE email=?", (email,))
        user = cursor.fetchone()

        conn.close()

        if user:
            token = serializer.dumps(email, salt='reset-senha')
            link = url_for('resetar_senha', token=token, _external=True)

            msg = Message(
                'Recuperação de Senha - SEMMADU',
                recipients=[email]
            )
            msg.body = f'Clique no link para redefinir sua senha:\n{link}'

            mail.send(msg)

        return "Se o email existir, um link foi enviado."

    return render_template('esqueci_senha.html')


# 🔄 RESET SENHA (CORRIGIDO)
@app.route('/resetar_senha/<token>', methods=['GET', 'POST'])
def resetar_senha(token):
    try:
        email = serializer.loads(token, salt='reset-senha', max_age=3600)
    except:
        return "Link inválido ou expirado"

    if request.method == 'POST':
        nova_senha = request.form['senha']

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE usuarios SET senha=? WHERE email=?",
            (nova_senha, email)
        )

        conn.commit()
        conn.close()

        return redirect(url_for('login'))

    return render_template('resetar_senha.html')


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

        cursor.execute("""
            INSERT INTO historico (denuncia_id, status, observacao)
            VALUES (?, ?, ?)
        """, (denuncia_id, "Recebido", "Denúncia criada"))

        conn.commit()
        conn.close()

        return redirect(url_for('index'))

    return render_template('denunciar.html')


# 🔒 PAINEL
@app.route('/painel')
def painel():
    if not session.get('logado'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM denuncias ORDER BY id DESC")
    dados = cursor.fetchall()

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


# 🔄 STATUS
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


# 📍 MAPA
@app.route('/mapa')
def mapa():
    if not session.get('logado'):
        return redirect('/login')
    return render_template('mapa.html')


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


@app.route('/dados_mapa')
def dados_mapa():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT id, tipo, descricao, localizacao, status FROM denuncias")
    dados = cursor.fetchall()

    conn.close()

    return jsonify([
        {
            "id": d[0],
            "tipo": d[1],
            "descricao": d[2],
            "localizacao": d[3],
            "status": d[4]
        } for d in dados
    ])


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

    cursor.execute("SELECT tipo, COUNT(*) FROM denuncias GROUP BY tipo")
    dados_tipo = cursor.fetchall()

    cursor.execute("SELECT status, COUNT(*) FROM denuncias GROUP BY status")
    dados_status = cursor.fetchall()

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