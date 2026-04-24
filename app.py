from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from database import conectar, criar_tabelas
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os

# 🔐 CARREGA VARIÁVEIS SEGURAS
load_dotenv()

app = Flask(__name__)

# 🔐 SEGURANÇA
app.secret_key = os.getenv('SECRET_KEY')

if not app.secret_key:
    raise Exception("SECRET_KEY não definida no .env")

# 📧 EMAIL (SEGURO)
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

# 👤 CADASTRAR USUÁRIO
@app.route('/cadastrar_usuario', methods=['GET', 'POST'])
def cadastrar_usuario():
    if not session.get('logado') or session.get('tipo') != 'admin':
        return "Acesso restrito"

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = generate_password_hash(request.form['senha'])
        tipo = request.form['tipo']

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO usuarios (nome, email, senha, tipo)
        VALUES (?, ?, ?, ?)
        """, (nome, email, senha, tipo))

        conn.commit()
        conn.close()

        return redirect('/usuarios')

    return render_template('cadastrar_usuario.html')

# 👥 LISTAR USUÁRIOS
@app.route('/usuarios')
def usuarios():
    if not session.get('logado') or session.get('tipo') != 'admin':
        return "Acesso restrito"

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT id, nome, email, tipo FROM usuarios")
    dados = cursor.fetchall()

    conn.close()

    return render_template('usuarios.html', dados=dados)

# ❌ DELETAR USUÁRIO
@app.route('/deletar_usuario/<int:id>')
def deletar_usuario(id):
    if not session.get('logado') or session.get('tipo') != 'admin':
        return "Acesso restrito"

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM usuarios WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect('/usuarios')

# 🔁 ESQUECI SENHA
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

            msg = Message('Recuperação de Senha - SEMMADU', recipients=[email])
            msg.body = f'Clique no link para redefinir sua senha:\n{link}'

            mail.send(msg)

        return "Se o email existir, um link foi enviado."

    return render_template('esqueci_senha.html')

# 🔄 RESET SENHA
@app.route('/resetar_senha/<token>', methods=['GET', 'POST'])
def resetar_senha(token):
    try:
        email = serializer.loads(token, salt='reset-senha', max_age=3600)
    except:
        return "Link inválido ou expirado"

    if request.method == 'POST':
        nova_senha = generate_password_hash(request.form['senha'])

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
        INSERT INTO historico (denuncia_id, status, observacao, usuario)
        VALUES (?, ?, ?, ?)
    """, (id, novo_status, "Atualizado pelo sistema", session.get('usuario', 'sistema')))

    conn.commit()
    conn.close()

    return redirect('/painel')

# 📊 DASHBOARD
@app.route('/dashboard')
def dashboard():
    if not session.get('logado'):
        return redirect('/login')
    return render_template('dashboard.html')

# 📊 DADOS DASHBOARD
@app.route('/dados_dashboard')
def dados_dashboard():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT status, COUNT(*) FROM denuncias GROUP BY status")
    status = cursor.fetchall()

    cursor.execute("SELECT tipo, COUNT(*) FROM denuncias GROUP BY tipo")
    tipos = cursor.fetchall()

    conn.close()

    return jsonify({
        "status": {
            "labels": [s[0] for s in status] if status else ["Sem dados"],
            "valores": [s[1] for s in status] if status else [0]
        },
        "tipos": {
            "labels": [t[0] for t in tipos] if tipos else ["Sem dados"],
            "valores": [t[1] for t in tipos] if tipos else [0]
        }
    })

# 🚀 RUN
if __name__ == '__main__':
    app.run()