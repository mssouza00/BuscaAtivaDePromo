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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_precos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            preco REAL NOT NULL,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
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
        DELETE FROM historico_precos
        WHERE produto_id = ?
    """, (produto_id,))

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


def salvar_historico_preco(produto_id, preco):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO historico_precos
        (produto_id, preco)
        VALUES (?, ?)
    """, (produto_id, preco))

    conn.commit()
    conn.close()


def buscar_historico_produto(chat_id, produto_id, limite=10):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            p.nome,
            h.preco,
            h.data_hora
        FROM historico_precos h
        INNER JOIN produtos p
            ON p.id = h.produto_id
        WHERE h.produto_id = ?
          AND p.chat_id = ?
        ORDER BY h.data_hora DESC
        LIMIT ?
    """, (produto_id, chat_id, limite))

    historico = cursor.fetchall()
    conn.close()

    return historico


def buscar_resumo_historico(chat_id, produto_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.nome,
            MIN(h.preco) AS menor_preco,
            MAX(h.preco) AS maior_preco,
            AVG(h.preco) AS preco_medio,
            COUNT(h.id) AS total_registros
        FROM historico_precos h
        INNER JOIN produtos p
            ON p.id = h.produto_id
        WHERE h.produto_id = ?
          AND p.chat_id = ?
        GROUP BY p.nome
    """, (produto_id, chat_id))

    resumo = cursor.fetchone()
    conn.close()

    return resumo