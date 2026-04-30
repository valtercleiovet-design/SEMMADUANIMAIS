import os
import psycopg2
from werkzeug.security import generate_password_hash

def conectar():
    return psycopg2.connect(
        os.getenv("DATABASE_URL"),
        sslmode='require'
    )

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    # 👤 USUÁRIOS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        nome TEXT,
        email TEXT UNIQUE,
        senha TEXT,
        tipo TEXT
    )
    """)

    # 🚨 DENÚNCIAS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS denuncias (
        id SERIAL PRIMARY KEY,
        tipo TEXT,
        descricao TEXT,
        localizacao TEXT,
        imagem TEXT,
        status TEXT,
        data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fiscal_id INTEGER,
        protocolo TEXT
    )
    """)

    # 📊 HISTÓRICO
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico (
        id SERIAL PRIMARY KEY,
        denuncia_id INTEGER,
        status TEXT,
        observacao TEXT,
        usuario TEXT,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 👑 ADMIN PADRÃO
    cursor.execute("SELECT * FROM usuarios WHERE email = %s", ('admin@admin.com',))
    admin = cursor.fetchone()

    if not admin:
        senha_hash = generate_password_hash('123')

        cursor.execute("""
        INSERT INTO usuarios (nome, email, senha, tipo)
        VALUES (%s, %s, %s, %s)
        """, ('Administrador', 'admin@admin.com', senha_hash, 'admin'))

    conn.commit()
    conn.close()