import sqlite3

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
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (denuncia_id) REFERENCES denuncias(id)
    )
    """)

    # 🔍 VERIFICA SE ADMIN EXISTE
    cursor.execute("SELECT * FROM usuarios WHERE email = ?", ('admin@admin.com',))
    user = cursor.fetchone()

    if not user:
        cursor.execute("""
        INSERT INTO usuarios (email, senha, nome, tipo)
        VALUES (?, ?, ?, ?)
        """, ('admin@admin.com', '123', 'Administrador', 'admin'))

    conn.commit()
    conn.close()