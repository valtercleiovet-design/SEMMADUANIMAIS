from datetime import datetime 
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
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
app.config['SESSION_COOKIE_SECURE'] = True

# EMAIL CONFIG
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
            token = serializer.dumps(email, salt='recuperacao-senha')
            link = url_for('resetar_senha', token=token, _external=True)

            msg = Message('Recuperação de senha - SEMMADU', recipients=[email])
            msg.body = f'Acesse o link para redefinir sua senha:\n\n{link}'
            mail.send(msg)

        return render_template('recuperar.html', mensagem="Se o email existir, o link foi enviado.")

    return render_template('recuperar.html')

@app.route('/resetar/<token>', methods=['GET', 'POST'])
def resetar_senha(token):
    try:
        email = serializer.loads(token, salt='recuperacao-senha', max_age=3600)
    except:
        return "Link inválido ou expirado"

    if request.method == 'POST':
        nova_senha = request.form['senha']
        senha_hash = generate_password_hash(nova_senha)

        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET senha=%s WHERE email=%s", (senha_hash, email))
        conn.commit()
        conn.close()

        return redirect('/login')

    return render_template('resetar.html')

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
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (tipo, descricao, localizacao, caminho_imagem, "RECEBIDO"))

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

@app.route('/cadastrar_usuario', methods=['GET', 'POST'])
def cadastrar_usuario():
    if not session.get('logado'):
        return redirect('/login')

    if session.get('tipo') != 'admin':
        return "Acesso negado"

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        tipo = request.form['tipo']

        senha_hash = generate_password_hash(senha)

        conn = conectar()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO usuarios (nome, email, senha, tipo)
                VALUES (%s, %s, %s, %s)
            """, (nome, email, senha_hash, tipo))

            conn.commit()
        except:
            conn.close()
            return "Erro: usuário já existe"

        conn.close()
        return redirect('/usuarios')

    return render_template('cadastrar_usuario.html')

@app.route('/mapa/<int:id>')
def mapa(id):
    if not session.get('logado'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT localizacao FROM denuncias WHERE id=%s", (id,))
    resultado = cursor.fetchone()

    conn.close()

    if not resultado:
        return "Denúncia não encontrada"

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

    cursor.execute("""
        SELECT id, tipo, descricao, localizacao, imagem, status
        FROM denuncias
    """)
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

@app.route('/atualizar_status/<int:id>/<novo_status>')
def atualizar_status(id, novo_status):
    if not session.get('logado'):
        return redirect('/login')

    mapa_status = {
        "EM_ATENDIMENTO": "EM_ATENDIMENTO",
        "FINALIZADO": "FINALIZADO"
    }

    if novo_status not in mapa_status:
        return redirect('/painel')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM denuncias WHERE id=%s", (id,))
    resultado = cursor.fetchone()

    if not resultado:
        conn.close()
        return redirect('/painel')

    status_atual = resultado[0]

    if status_atual in ["FINALIZADO", "NAO_ATENDIDO"]:
        conn.close()
        return redirect('/painel')

    if status_atual == "RECEBIDO" and novo_status != "EM_ATENDIMENTO":
        conn.close()
        return redirect('/painel')

    if status_atual == "EM_ATENDIMENTO" and novo_status != "FINALIZADO":
        conn.close()
        return redirect('/painel')

    cursor.execute(
        "UPDATE denuncias SET status=%s WHERE id=%s",
        (novo_status, id)
    )

    cursor.execute("""
        INSERT INTO historico (denuncia_id, status, observacao, usuario)
        VALUES (%s, %s, %s, %s)
    """, (id, novo_status, "Atualizado pelo sistema", session.get('usuario')))

    conn.commit()
    conn.close()

    return redirect('/painel')

@app.route('/excluir_usuario/<int:id>')
def excluir_usuario(id):
    if not session.get('logado'):
        return redirect('/login')

    if session.get('tipo') != 'admin':
        return "Acesso negado"

    if id == session.get('usuario_id'):
        return "Você não pode excluir seu próprio usuário"

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM usuarios WHERE id=%s", (id,))
    conn.commit()
    conn.close()

    return redirect('/usuarios')

@app.route('/nao_atendido/<int:id>', methods=['POST'])
def nao_atendido(id):
    if not session.get('logado'):
        return redirect('/login')

    motivo = request.form['motivo']

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE denuncias
        SET status = 'NAO_ATENDIDO'
        WHERE id = %s
    """, (id,))

    cursor.execute("""
        INSERT INTO historico (denuncia_id, status, observacao, usuario)
        VALUES (%s, %s, %s, %s)
    """, (id, "NAO_ATENDIDO", motivo, session.get('usuario')))

    conn.commit()
    conn.close()

    return redirect('/painel')

@app.route('/gerar_pdf/<int:id>')
def gerar_pdf(id):
    if not session.get('logado'):
        return redirect('/login')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, tipo, descricao, localizacao, status
        FROM denuncias
        WHERE id=%s
    """, (id,))
    d = cursor.fetchone()

    conn.close()

    if not d:
        return "Denúncia não encontrada"

    file_path = f"static/relatorio_{id}.pdf"

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()

    conteudo = []

    conteudo.append(Paragraph("ESTADO DE RONDÔNIA", styles['Title']))
    conteudo.append(Paragraph("PREFEITURA MUNICIPAL DE ROLIM DE MOURA", styles['Normal']))
    conteudo.append(Paragraph("SEMMADU - Departamento de Políticas Públicas Relacionadas ao Bem-Estar Animal", styles['Normal']))
    conteudo.append(Spacer(1, 12))

    conteudo.append(Paragraph(f"<b>Resumo Técnico Preliminar Nº {d[0]}</b>", styles['Title']))
    conteudo.append(Spacer(1, 10))

    conteudo.append(Paragraph(
        "<font color='red'><b>ATENÇÃO:</b> Documento auxiliar gerado automaticamente. Não substitui relatório técnico oficial.</font>",
        styles['Normal']
    ))

    conteudo.append(Spacer(1, 12))

    conteudo.append(Paragraph(f"<b>Tipo:</b> {d[1]}", styles['Normal']))
    conteudo.append(Paragraph(f"<b>Local:</b> {d[3]}", styles['Normal']))
    conteudo.append(Paragraph(f"<b>Status:</b> {d[4]}", styles['Normal']))
    conteudo.append(Spacer(1, 12))

    conteudo.append(Paragraph("<b>DESCRIÇÃO:</b>", styles['Heading2']))
    conteudo.append(Paragraph(d[2], styles['Normal']))
    conteudo.append(Spacer(1, 12))

    conteudo.append(Paragraph("<b>BASE LEGAL:</b>", styles['Heading2']))
    conteudo.append(Paragraph("- Lei Federal nº 9.605/98 (Crimes Ambientais)", styles['Normal']))
    conteudo.append(Paragraph("- Lei Complementar Municipal nº 254/2018 (Bem-estar animal)", styles['Normal']))
    conteudo.append(Paragraph("- Lei Municipal nº 1677/2009 (Programa de Proteção Animal)", styles['Normal']))
    conteudo.append(Paragraph("- Lei Estadual nº 6.016/2025 (proibição de acorrentamento)", styles['Normal']))
    conteudo.append(Spacer(1, 20))

    if d[4] == "FINALIZADO":
        conclusao = "A denúncia foi atendida e devidamente finalizada."
    elif d[4] == "NAO_ATENDIDO":
        conclusao = "A denúncia não pôde ser atendida, conforme justificativa registrada."
    else:
        conclusao = "A denúncia encontra-se em andamento."

    conteudo.append(Paragraph("<b>CONCLUSÃO:</b>", styles['Heading2']))
    conteudo.append(Paragraph(conclusao, styles['Normal']))

    conteudo.append(Spacer(1, 30))

    conteudo.append(Paragraph("__________________________________", styles['Normal']))
    conteudo.append(Paragraph(session.get('usuario'), styles['Normal']))
    conteudo.append(Paragraph("Médico Veterinário / Responsável Técnico", styles['Normal']))
    conteudo.append(Spacer(1, 20))
    conteudo.append(Paragraph(
        "<font size=8 color='grey'>Documento gerado automaticamente pelo sistema SEMMADU</font>",
        styles['Normal']
    ))

    doc.build(conteudo)

    return redirect(f"/static/relatorio_{id}.pdf")

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
            WHERE protocolo = %s
        """, (protocolo,))

        resultado = cursor.fetchone()
        conn.close()

    return render_template('consulta.html', resultado=resultado)

if __name__ == '__main__':
    app.run()