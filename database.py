import sqlite3

DB_NAME = "produtos.db"


def conectar():
    return sqlite3.connect(DB_NAME)


def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            url TEXT NOT NULL,
            preco_alvo REAL NOT NULL,
            ultimo_preco REAL,
            alerta_enviado INTEGER DEFAULT 0,
            ativo INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()


def adicionar_produto(chat_id, nome, url, preco_alvo):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO produtos 
        (chat_id, nome, url, preco_alvo)
        VALUES (?, ?, ?, ?)
    """, (chat_id, nome, url, preco_alvo))

    conn.commit()
    conn.close()


def listar_produtos(chat_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nome, url, preco_alvo, ultimo_preco, ativo
        FROM produtos
        WHERE chat_id = ?
        ORDER BY id DESC
    """, (chat_id,))

    produtos = cursor.fetchall()
    conn.close()

    return produtos


def remover_produto(chat_id, produto_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM produtos
        WHERE id = ? AND chat_id = ?
    """, (produto_id, chat_id))

    conn.commit()
    conn.close()


def buscar_produtos_ativos():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, chat_id, nome, url, preco_alvo, ultimo_preco, alerta_enviado
        FROM produtos
        WHERE ativo = 1
    """)

    produtos = cursor.fetchall()
    conn.close()

    return produtos


def atualizar_preco(produto_id, preco):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE produtos
        SET ultimo_preco = ?
        WHERE id = ?
    """, (preco, produto_id))

    conn.commit()
    conn.close()


def marcar_alerta(produto_id, enviado):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE produtos
        SET alerta_enviado = ?
        WHERE id = ?
    """, (enviado, produto_id))

    conn.commit()
    conn.close()
