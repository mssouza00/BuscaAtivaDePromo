import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import (
    criar_tabela,
    adicionar_produto,
    listar_produtos,
    remover_produto
)
from price_checker import checar_precos


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", 60))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = """
Olá! Eu sou seu bot de monitoramento de preços.

Comandos disponíveis:

/adicionar Nome | Link | PreçoAlvo
/listar
/remover ID
/checar

Exemplo:
/adicionar Mouse Gamer | https://site.com/produto | 150
"""
    await update.message.reply_text(mensagem)


async def adicionar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    texto = update.message.text.replace("/adicionar", "").strip()

    try:
        nome, url, preco = texto.split("|")

        nome = nome.strip()
        url = url.strip()
        preco = float(
            preco.strip()
            .replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
        )

        adicionar_produto(chat_id, nome, url, preco)

        await update.message.reply_text(
            f"✅ Produto cadastrado!\n\n"
            f"Nome: {nome}\n"
            f"Preço alvo: R$ {preco:.2f}"
        )

    except Exception:
        await update.message.reply_text(
            "Formato inválido.\n\n"
            "Use assim:\n"
            "/adicionar Nome | Link | PreçoAlvo\n\n"
            "Exemplo:\n"
            "/adicionar Mouse Gamer | https://site.com/produto | 150"
        )


async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    produtos = listar_produtos(chat_id)

    if not produtos:
        await update.message.reply_text("Você ainda não cadastrou produtos.")
        return

    mensagem = "📦 Produtos cadastrados:\n\n"

    for produto in produtos:
        produto_id, nome, url, preco_alvo, ultimo_preco, ativo = produto

        ultimo = f"R$ {ultimo_preco:.2f}" if ultimo_preco is not None else "Ainda não checado"
        status = "Ativo" if ativo == 1 else "Pausado"

        mensagem += (
            f"ID: {produto_id}\n"
            f"Nome: {nome}\n"
            f"Preço alvo: R$ {preco_alvo:.2f}\n"
            f"Último preço: {ultimo}\n"
            f"Status: {status}\n"
            f"Link: {url}\n\n"
        )

    await update.message.reply_text(mensagem)


async def remover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    try:
        produto_id = int(context.args[0])
        remover_produto(chat_id, produto_id)

        await update.message.reply_text(f"🗑 Produto ID {produto_id} removido.")

    except Exception:
        await update.message.reply_text(
            "Use assim:\n/remover ID\n\n"
            "Exemplo:\n/remover 1"
        )


async def checar_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Checando preços agora...")
    await checar_precos(context.application)
    await update.message.reply_text("✅ Checagem finalizada.")


async def checar_agendado(app):
    logging.info("Executando checagem agendada...")
    await checar_precos(app)


def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_TOKEN não encontrado. Configure essa variável no Railway.")

    criar_tabela()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("adicionar", adicionar))
    app.add_handler(CommandHandler("listar", listar))
    app.add_handler(CommandHandler("remover", remover))
    app.add_handler(CommandHandler("checar", checar_manual))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        checar_agendado,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        args=[app]
    )
    scheduler.start()

    logging.info("Bot iniciado no Railway...")
    app.run_polling()


if __name__ == "__main__":
    main()
