import sqlite3
from werkzeug.security import generate_password_hash

def conectar():
    return sqlite3.connect('banco.db')


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