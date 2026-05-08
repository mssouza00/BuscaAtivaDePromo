import os
import logging
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup
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


def menu_principal():
    teclado = [
        ["/listar", "/checar"],
        ["/adicionar", "/remover"],
        ["/start"]
    ]

    return ReplyKeyboardMarkup(
        teclado,
        resize_keyboard=True
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = """
Olá! Eu sou seu bot de monitoramento de preços.

Use o menu abaixo ou digite os comandos:

/adicionar Nome | Link | PreçoAlvo
/listar
/remover ID
/checar

Exemplo:
/adicionar tv | https://www.amazon.com.br/dp/B0GH2SC1XG | 1500
"""

    await update.message.reply_text(
        mensagem,
        reply_markup=menu_principal()
    )


async def adicionar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    texto = update.message.text.replace("/adicionar", "").strip()

    try:
        partes = texto.split("|")

        if len(partes) != 3:
            raise ValueError("Formato inválido. Separe nome, link e preço usando |")

        nome, url, preco = partes

        nome = nome.strip()
        url = url.strip()
        preco = preco.strip()

        if not nome:
            raise ValueError("Nome do produto vazio.")

        if not url.startswith("http"):
            raise ValueError("Link inválido. O link precisa começar com http ou https.")

        preco = float(
            preco
            .replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
        )

        adicionar_produto(chat_id, nome, url, preco)

        await update.message.reply_text(
            f"✅ Produto cadastrado!\n\n"
            f"Nome: {nome}\n"
            f"Preço alvo: R$ {preco:.2f}",
            reply_markup=menu_principal()
        )

    except Exception as erro:
        await update.message.reply_text(
            f"❌ Erro ao adicionar produto:\n{erro}\n\n"
            "Use assim:\n"
            "/adicionar Nome | Link | PreçoAlvo\n\n"
            "Exemplo:\n"
            "/adicionar tv | https://www.amazon.com.br/dp/B0GH2SC1XG | 1500",
            reply_markup=menu_principal()
        )


async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    produtos = listar_produtos(chat_id)

    if not produtos:
        await update.message.reply_text(
            "Você ainda não cadastrou produtos.",
            reply_markup=menu_principal()
        )
        return

    mensagem = "📦 Produtos cadastrados:\n\n"

    for produto in produtos:
        produto_id, nome, url, preco_alvo, ultimo_preco, ativo = produto

        ultimo = (
            f"R$ {ultimo_preco:.2f}"
            if ultimo_preco is not None
            else "Ainda não checado"
        )

        status = "Ativo" if ativo == 1 else "Pausado"

        mensagem += (
            f"ID: {produto_id}\n"
            f"Nome: {nome}\n"
            f"Preço alvo: R$ {preco_alvo:.2f}\n"
            f"Último preço: {ultimo}\n"
            f"Status: {status}\n"
            f"Link: {url}\n\n"
        )

    await update.message.reply_text(
        mensagem,
        reply_markup=menu_principal()
    )


async def remover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    try:
        produto_id = int(context.args[0])
        remover_produto(chat_id, produto_id)

        await update.message.reply_text(
            f"🗑 Produto ID {produto_id} removido.",
            reply_markup=menu_principal()
        )

    except Exception:
        await update.message.reply_text(
            "Use assim:\n/remover ID\n\n"
            "Exemplo:\n/remover 1",
            reply_markup=menu_principal()
        )


async def checar_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    await update.message.reply_text(
        "🔎 Checando preços agora...",
        reply_markup=menu_principal()
    )

    resultados = await checar_precos(
        context.application,
        chat_id_manual=chat_id
    )

    if not resultados:
        await update.message.reply_text(
            "Você ainda não tem produtos cadastrados.",
            reply_markup=menu_principal()
        )
        return

    mensagem = "✅ Resultado da checagem:\n\n"
    mensagem += "\n\n--------------------\n\n".join(resultados)

    await update.message.reply_text(
        mensagem,
        reply_markup=menu_principal()
    )


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