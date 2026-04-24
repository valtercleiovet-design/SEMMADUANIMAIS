import sqlite3

def conectar():
    return sqlite3.connect('banco.db')

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    # 🔐 TABELA DE USUÁRIOS (LOGIN)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE,
        senha TEXT
    )
    """)

    # 🚨 TABELA DE DENÚNCIAS (MELHORADA)
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

    # 📊 HISTÓRICO DE MOVIMENTAÇÃO (NÍVEL PROFISSIONAL)
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

    # 👤 INSERE USUÁRIO PADRÃO (SE NÃO EXISTIR)
    cursor.execute("""
    INSERT OR IGNORE INTO usuarios (usuario, senha)
    VALUES ('admin', '123')
    """)

    conn.commit()
    conn.close()