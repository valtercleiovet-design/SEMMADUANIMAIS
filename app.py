from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from flask_mail import Mail
from itsdangerous import URLSafeTimedSerializer
from flask import Flask, render_template, request, redirect, url_for, session
from database import conectar, criar_tabelas
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
import base64

print("🔥 ESSE APP.PY ESTÁ RODANDO 🔥")

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

if not app.secret_key:
    raise Exception("SECRET_KEY não definida")

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True

# EMAIL
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('EMAIL_USER')

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# CRIA TABELAS
criar_tabelas()

# ---------------------- ROTAS ----------------------

@app.route('/')
def index():
    return render_template('index.html')

# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM usuarios WHERE email=%s", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], senha):
            session['logado'] = True
            session['usuario'] = user[1]
            session['tipo'] = user[4]
            session['usuario_id'] = user[0]
            return redirect(url_for('painel'))

        return render_template('login.html', erro="Usuário ou senha inválidos")

    return render_template('login.html')

# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# DENÚNCIA
@app.route('/denunciar', methods=['GET', 'POST'])
def denunciar():
    if request.method == 'POST':
        descricao = request.form['descricao']
        tipo = request.form['tipo']
        localizacao = request.form['localizacao']

        arquivo = request.files.get('imagem')
        imagem_base64 = None

        if arquivo and arquivo.filename != '':
            imagem_base64 = base64.b64encode(arquivo.read()).decode('utf-8')

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO denuncias (tipo, descricao, localizacao, imagem, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (tipo, descricao, localizacao, imagem_base64, "RECEBIDO"))

        denuncia_id = cursor.fetchone()[0]

        ano = datetime.now().year
        protocolo = f"SEM-{ano}-{denuncia_id:06d}"

        cursor.execute("UPDATE denuncias SET protocolo=%s WHERE id=%s", (protocolo, denuncia_id))

        cursor.execute("""
            INSERT INTO historico (denuncia_id, status, observacao, usuario)
            VALUES (%s, %s, %s, %s)
        """, (denuncia_id, "RECEBIDO", "Denúncia criada", session.get('usuario', 'anonimo')))

        conn.commit()
        conn.close()

        return render_template('sucesso.html', protocolo=protocolo)

    return render_template('denunciar.html')

# PAINEL
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

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE status='RECEBIDO'")
    recebido = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE status='EM_ATENDIMENTO'")
    fiscalizacao = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE status='FINALIZADO'")
    resolvido = cursor.fetchone()[0]

    cursor.execute("SELECT id, nome FROM usuarios WHERE tipo='fiscal'")
    fiscais = cursor.fetchall()

    conn.close()

    return render_template('painel.html',
                           dados=dados,
                           total=total,
                           recebido=recebido,
                           fiscalizacao=fiscalizacao,
                           resolvido=resolvido,
                           fiscais=fiscais)

# USUÁRIOS
@app.route('/usuarios')
def usuarios():
    if not session.get('usuario'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios")
    dados = cursor.fetchall()

    conn.close()

    return render_template('usuarios.html', dados=dados)

# CADASTRAR USUÁRIO (CORRIGIDO)
@app.route('/cadastrar_usuario', methods=['GET', 'POST'])
def cadastrar_usuario():
    if not session.get('usuario') or session.get('tipo') != 'admin':
        return redirect('/painel')

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        tipo = request.form['tipo']

        senha_hash = generate_password_hash(senha)

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO usuarios (nome, email, senha, tipo)
            VALUES (%s, %s, %s, %s)
        """, (nome, email, senha_hash, tipo))

        conn.commit()
        conn.close()

        return redirect('/usuarios')

    return render_template('cadastrar_usuario.html')

# EXCLUIR USUÁRIO
@app.route('/excluir_usuario/<int:id>')
def excluir_usuario(id):
    if not session.get('usuario') or session.get('tipo') != 'admin':
        return redirect('/painel')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM usuarios WHERE id=%s", (id,))

    conn.commit()
    conn.close()

    return redirect('/usuarios')

# MAPA
@app.route('/mapa/<int:id>')
def mapa(id):
    if not session.get('logado'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT localizacao FROM denuncias WHERE id=%s", (id,))
    resultado = cursor.fetchone()

    conn.close()

    return render_template('mapa.html', localizacao=resultado[0])

# HISTÓRICO
@app.route('/historico/<int:id>')
def historico(id):
    if not session.get('logado'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status, observacao, usuario, data
        FROM historico
        WHERE denuncia_id=%s
        ORDER BY data DESC
    """, (id,))

    dados = cursor.fetchall()
    conn.close()

    return render_template('historico.html', dados=dados)

# DASHBOARD
@app.route('/dashboard')
def dashboard():
    if not session.get('logado'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT id, tipo, descricao, localizacao, imagem, status FROM denuncias")
    dados = cursor.fetchall()

    total = len(dados)
    recebido = len([d for d in dados if d[5] == 'RECEBIDO'])
    fiscalizacao = len([d for d in dados if d[5] == 'EM_ATENDIMENTO'])
    resolvido = len([d for d in dados if d[5] == 'FINALIZADO'])

    conn.close()

    return render_template(
        'dashboard.html',
        total=total,
        recebido=recebido,
        fiscalizacao=fiscalizacao,
        resolvido=resolvido,
        dados=dados
    )

# PDF (placeholder)
@app.route('/gerar_pdf/<int:id>')
def gerar_pdf(id):
    if not session.get('usuario'):
        return redirect('/login')

    return f"PDF da denúncia {id} (em desenvolvimento)"

# ----------------------

if __name__ == '__main__':
    app.run(debug=True)