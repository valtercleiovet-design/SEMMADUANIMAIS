from datetime import datetime 
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
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
app.config['SESSION_COOKIE_SECURE'] = False

# EMAIL CONFIG
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('EMAIL_USER')

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

criar_tabelas()

@app.route('/')
def index():
    return render_template('index.html')

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
        else:
            return render_template('login.html', erro="Usuário ou senha inválidos")

    return render_template('login.html')
@app.route('/recuperar', methods=['GET', 'POST'])
def recuperar():
    if request.method == 'POST':
        email = request.form['email']

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
        user = cursor.fetchone()

        conn.close()

        if user:
            return render_template('recuperar.html', mensagem="Email encontrado. Em breve enviaremos instruções.")

        return render_template('recuperar.html', mensagem="Email não encontrado.")

    return render_template('recuperar.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/denunciar', methods=['GET', 'POST'])
def denunciar():
    if request.method == 'POST':
        descricao = request.form['descricao']
        tipo = request.form['tipo']
        localizacao = request.form['localizacao']

        # 🔥 NOVO: salva imagem em base64
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

        cursor.execute("""
            UPDATE denuncias SET protocolo=%s WHERE id=%s
        """, (protocolo, denuncia_id))

        cursor.execute("""
            INSERT INTO historico (denuncia_id, status, observacao, usuario)
            VALUES (%s, %s, %s, %s)
        """, (denuncia_id, "RECEBIDO", "Denúncia criada", session.get('usuario', 'anonimo')))

        conn.commit()
        conn.close()

        return render_template('sucesso.html', protocolo=protocolo)

    return render_template('denunciar.html')

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

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE status = 'RECEBIDO'")
    recebido = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE status = 'EM_ATENDIMENTO'")
    fiscalizacao = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM denuncias WHERE status = 'FINALIZADO'")
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

@app.route('/usuarios')
def usuarios():
    if 'usuario' not in session:
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios")
    dados = cursor.fetchall()

    conn.close()

    return render_template('usuarios.html', dados=dados)

@app.route('/gerar_pdf/<int:id>')
def gerar_pdf(id):
    if 'usuario' not in session:
        return redirect('/login')

    return f"PDF da denúncia {id} (em desenvolvimento)"

#CADASTAR USUÁRIO

@app.route('/cadastrar_usuario', methods=['GET', 'POST'])
def cadastrar_usuario():
    if 'usuario' not in session or session.get('tipo') != 'admin':
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

#EXCLUIR USUÁRIO

@app.route('/excluir_usuario/<int:id>')
def excluir_usuario(id):
    if 'usuario' not in session or session.get('tipo') != 'admin':
        return redirect('/painel')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM usuarios WHERE id=%s", (id,))

    conn.commit()
    conn.close()

    return redirect('/usuarios')

@app.route('/usuarios/novo', methods=['GET', 'POST'])
def cadastrar_usuario():
    return render_template('novo_usuario.html')

#USUÁRIO NOVO

@app.route('/usuarios/novo', methods=['GET', 'POST'])
def cadastrar_usuario():

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        tipo = request.form['tipo']

        conn = sqlite3.connect('banco.db')
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO usuarios (nome, email, senha, tipo)
            VALUES (?, ?, ?, ?)
        """, (nome, email, senha, tipo))

        conn.commit()
        conn.close()

        return redirect(url_for('usuarios'))

    return render_template('novo_usuario.html')

@app.route('/consulta', methods=['GET', 'POST'])
def consulta():
    resultado = None

    if request.method == 'POST':
        protocolo = request.form['protocolo']

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT tipo, descricao, status
            FROM denuncias
            WHERE protocolo=%s
        """, (protocolo,))

        resultado = cursor.fetchone()
        conn.close()

    return render_template('consulta.html', resultado=resultado)

@app.route('/atualizar_status/<int:id>/<status>')
def atualizar_status(id, status):
    if not session.get('usuario'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("UPDATE denuncias SET status=%s WHERE id=%s", (status, id))

    cursor.execute("""
        INSERT INTO historico (denuncia_id, status, observacao, usuario)
        VALUES (%s, %s, %s, %s)
    """, (id, status, "Status atualizado", session.get('usuario')))

    conn.commit()
    conn.close()

    return redirect('/painel')


@app.route('/nao_atendido/<int:id>', methods=['POST'])
def nao_atendido(id):
    if not session.get('usuario'):
        return redirect('/login')

    motivo = request.form['motivo']

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("UPDATE denuncias SET status='NAO_ATENDIDO' WHERE id=%s", (id,))

    cursor.execute("""
        INSERT INTO historico (denuncia_id, status, observacao, usuario)
        VALUES (%s, %s, %s, %s)
    """, (id, "NAO_ATENDIDO", motivo, session.get('usuario')))

    conn.commit()
    conn.close()

    return redirect('/painel')


if __name__ == '__main__':
    app.run()