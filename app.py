from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from database import conectar, criar_tabelas
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import uuid

print("🔥 ESSE APP.PY ESTÁ RODANDO 🔥")

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv('SECRET_KEY')

if not app.secret_key:
    raise Exception("SECRET_KEY não definida")

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('EMAIL_USER')

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

criar_tabelas()

# 🔓 HOME
@app.route('/')
def index():
    return render_template('index.html')

# 🔧 TESTE (OBRIGATÓRIO PRA DEBUG)
@app.route('/teste')
def teste():
    return "FUNCIONANDO OK"

# 🔐 LOGIN
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

        if user and check_password_hash(user[3], senha):
            session['logado'] = True
            session['usuario'] = user[1]
            session['tipo'] = user[4]
            return redirect(url_for('painel'))
        else:
            return render_template('login.html', erro="Usuário ou senha inválidos")

    return render_template('login.html')

# 🚪 LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

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
            nome_seguro = secure_filename(arquivo.filename)
            nome_final = f"{uuid.uuid4()}_{nome_seguro}"
            caminho_imagem = os.path.join(UPLOAD_FOLDER, nome_final)
            arquivo.save(caminho_imagem)

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO denuncias (tipo, descricao, localizacao, imagem, status)
            VALUES (?, ?, ?, ?, ?)
        """, (tipo, descricao, localizacao, caminho_imagem, "Recebido"))

        denuncia_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO historico (denuncia_id, status, observacao, usuario)
            VALUES (?, ?, ?, ?)
        """, (denuncia_id, "Recebido", "Denúncia criada", session.get('usuario', 'anonimo')))

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

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE LOWER(status) = 'recebido'")
    recebido = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM denuncias 
        WHERE LOWER(status) IN ('em fiscalização','em fiscalizacao')
    """)
    fiscalizacao = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE LOWER(status) = 'resolvido'")
    resolvido = cursor.fetchone()[0]

    conn.close()

    return render_template('painel.html',
                           dados=dados,
                           total=total,
                           recebido=recebido,
                           fiscalizacao=fiscalizacao,
                           resolvido=resolvido)

# 👥 USUÁRIOS
@app.route('/usuarios')
def usuarios():
    if not session.get('logado'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT id, nome, email, tipo FROM usuarios")
    dados = cursor.fetchall()

    conn.close()

    return render_template('usuarios.html', dados=dados)

# 🔄 STATUS
@app.route('/atualizar_status/<int:id>/<novo_status>')
def atualizar_status(id, novo_status):
    if not session.get('logado'):
        return redirect('/login')

    novo_status = novo_status.replace("_", " ").lower()

    mapa_status = {
        "recebido": "Recebido",
        "em fiscalizacao": "Em fiscalização",
        "resolvido": "Resolvido"
    }

    if novo_status not in mapa_status:
        return redirect('/painel')

    novo_status_formatado = mapa_status[novo_status]

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM denuncias WHERE id=?", (id,))
    resultado = cursor.fetchone()

    if not resultado:
        conn.close()
        return redirect('/painel')

    status_atual = resultado[0]
    status_atual_norm = status_atual.lower().replace("ç", "c")

    if status_atual_norm == "resolvido":
        conn.close()
        return redirect('/painel')

    if status_atual_norm == "recebido" and novo_status != "em fiscalizacao":
        conn.close()
        return redirect('/painel')

    if status_atual_norm == "em fiscalizacao" and novo_status != "resolvido":
        conn.close()
        return redirect('/painel')

    if status_atual_norm == novo_status:
        conn.close()
        return redirect('/painel')

    cursor.execute("UPDATE denuncias SET status=? WHERE id=?", (novo_status_formatado, id))

    cursor.execute("""
        INSERT INTO historico (denuncia_id, status, observacao, usuario)
        VALUES (?, ?, ?, ?)
    """, (id, novo_status_formatado, "Atualizado pelo sistema", session.get('usuario', 'sistema')))

    conn.commit()
    conn.close()

    return redirect('/painel')

# 📊 PÁGINA DASHBOARD
@app.route('/dashboard')
def dashboard():
    if not session.get('logado'):
        return redirect('/login')
    return render_template('dashboard.html')

# 📊 DADOS DASHBOARD
@app.route('/dados_dashboard')
def dados_dashboard():
    if not session.get('logado'):
        return jsonify({"erro": "não autorizado"})

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE LOWER(status) = 'recebido'")
    recebido = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM denuncias 
        WHERE LOWER(status) IN ('em fiscalização','em fiscalizacao')
    """)
    fiscalizacao = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE LOWER(status) = 'resolvido'")
    resolvido = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(TRIM(tipo), 'Não informado'), COUNT(*)
        FROM denuncias
        GROUP BY TRIM(tipo)
    """)

    tipos = cursor.fetchall()

    conn.close()

    return jsonify({
        "status_labels": ["Recebido", "Em fiscalização", "Resolvido"],
        "status_valores": [recebido, fiscalizacao, resolvido],
        "tipos_labels": [t[0] for t in tipos],
        "tipos_valores": [t[1] for t in tipos]
    })

# 📍 MAPA
@app.route('/mapa/<int:id>')
def mapa(id):
    if not session.get('logado'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT localizacao FROM denuncias WHERE id=?", (id,))
    resultado = cursor.fetchone()

    conn.close()

    return render_template('mapa.html', localizacao=resultado[0] if resultado else "")


# 📜 HISTÓRICO
@app.route('/historico/<int:id>')
def historico(id):
    if not session.get('logado'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status, observacao, usuario, data
        FROM historico
        WHERE denuncia_id=?
        ORDER BY data DESC
    """, (id,))

    dados = cursor.fetchall()

    conn.close()

    return render_template('historico.html', dados=dados)

# 🚀 RUN
if __name__ == '__main__':
    app.run(debug=True)