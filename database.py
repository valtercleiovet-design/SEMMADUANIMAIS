import sqlite3
from werkzeug.security import generate_password_hash
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def conectar():
    return sqlite3.connect(os.path.join(BASE_DIR, 'banco.db'))

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    # 👤 USUÁRIOS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        email TEXT UNIQUE,
        senha TEXT,
        tipo TEXT
    )
    """)

    # 🚨 DENÚNCIAS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS denuncias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT,
        descricao TEXT,
        localizacao TEXT,
        imagem TEXT,
        status TEXT,
        data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 🔥 GARANTIR COLUNA fiscal_id (SEM QUEBRAR BANCO EXISTENTE)
    cursor.execute("PRAGMA table_info(denuncias)")
    colunas = [col[1] for col in cursor.fetchall()]

    if "fiscal_id" not in colunas:
        cursor.execute("ALTER TABLE denuncias ADD COLUMN fiscal_id INTEGER")

    # 📊 HISTÓRICO
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        denuncia_id INTEGER,
        status TEXT,
        observacao TEXT,
        usuario TEXT,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (denuncia_id) REFERENCES denuncias(id)
    )
    """)

    # 👑 ADMIN PADRÃO (CRIPTOGRAFADO)
    cursor.execute("SELECT * FROM usuarios WHERE email = ?", ('admin@admin.com',))
    admin = cursor.fetchone()

    if not admin:
        senha_hash = generate_password_hash('123')

        cursor.execute("""
        INSERT INTO usuarios (nome, email, senha, tipo)
        VALUES (?, ?, ?, ?)
        """, ('Administrador', 'admin@admin.com', senha_hash, 'admin'))

    conn.commit()
    conn.close()