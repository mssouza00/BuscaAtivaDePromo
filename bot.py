import os
import logging
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
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

NOME, LINK, PRECO, REMOVER_ID = range(4)


def menu_principal():
    teclado = [
        ["➕ Adicionar produto", "📦 Listar produtos"],
        ["🔎 Checar preços", "🗑 Remover produto"],
        ["/start"]
    ]

    return ReplyKeyboardMarkup(
        teclado,
        resize_keyboard=True
    )


def menu_cancelar():
    teclado = [["❌ Cancelar"]]

    return ReplyKeyboardMarkup(
        teclado,
        resize_keyboard=True
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = """
Olá! Eu sou seu bot de monitoramento de preços.

Use o menu abaixo para controlar seus produtos.

Você pode:
➕ Adicionar produto
📦 Listar produtos
🔎 Checar preços
🗑 Remover produto
"""

    await update.message.reply_text(
        mensagem,
        reply_markup=menu_principal()
    )


async def iniciar_adicao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "➕ Vamos cadastrar um produto.\n\nQual o nome do produto?",
        reply_markup=menu_cancelar()
    )

    return NOME


async def receber_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()

    if nome == "❌ Cancelar":
        return await cancelar(update, context)

    if not nome:
        await update.message.reply_text("Nome inválido. Envie o nome do produto.")
        return NOME

    context.user_data["nome"] = nome

    await update.message.reply_text(
        "Agora envie o link do produto."
    )

    return LINK


async def receber_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if url == "❌ Cancelar":
        return await cancelar(update, context)

    if not url.startswith("http"):
        await update.message.reply_text(
            "Link inválido. Envie um link começando com http ou https."
        )
        return LINK

    context.user_data["url"] = url

    await update.message.reply_text(
        "Agora envie o preço alvo.\n\nExemplo: 1500"
    )

    return PRECO


async def receber_preco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_preco = update.message.text.strip()

    if texto_preco == "❌ Cancelar":
        return await cancelar(update, context)

    try:
        preco = float(
            texto_preco
            .replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
        )

        if preco <= 0:
            raise ValueError("Preço precisa ser maior que zero.")

        chat_id = update.message.chat_id
        nome = context.user_data["nome"]
        url = context.user_data["url"]

        adicionar_produto(chat_id, nome, url, preco)

        await update.message.reply_text(
            f"✅ Produto cadastrado!\n\n"
            f"Nome: {nome}\n"
            f"Preço alvo: R$ {preco:.2f}\n"
            f"Link: {url}",
            reply_markup=menu_principal()
        )

        context.user_data.clear()

        return ConversationHandler.END

    except Exception:
        await update.message.reply_text(
            "Preço inválido.\n\nEnvie apenas o valor.\nExemplo: 1500"
        )
        return PRECO


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


async def iniciar_remocao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    produtos = listar_produtos(chat_id)

    if not produtos:
        await update.message.reply_text(
            "Você ainda não tem produtos para remover.",
            reply_markup=menu_principal()
        )
        return ConversationHandler.END

    mensagem = "🗑 Qual produto deseja remover?\n\n"

    for produto in produtos:
        produto_id, nome, url, preco_alvo, ultimo_preco, ativo = produto
        mensagem += f"ID: {produto_id} - {nome}\n"

    mensagem += "\nEnvie apenas o ID do produto."

    await update.message.reply_text(
        mensagem,
        reply_markup=menu_cancelar()
    )

    return REMOVER_ID


async def receber_id_remocao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()

    if texto == "❌ Cancelar":
        return await cancelar(update, context)

    try:
        produto_id = int(texto)
        chat_id = update.message.chat_id

        remover_produto(chat_id, produto_id)

        await update.message.reply_text(
            f"🗑 Produto ID {produto_id} removido.",
            reply_markup=menu_principal()
        )

        return ConversationHandler.END

    except Exception:
        await update.message.reply_text(
            "ID inválido. Envie apenas o número do produto."
        )
        return REMOVER_ID


async def checar_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    await update.message.reply_text(
        "🔎 Checando preços...",
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

    mensagem = "✅ Resultado:\n\n"
    mensagem += "\n\n--------------------\n\n".join(resultados)

    await update.message.reply_text(
        mensagem,
        reply_markup=menu_principal()
    )


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "Operação cancelada.",
        reply_markup=menu_principal()
    )

    return ConversationHandler.END


async def comando_antigo_adicionar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Agora o cadastro é guiado.\n\nClique em ➕ Adicionar produto ou envie /adicionar.",
        reply_markup=menu_principal()
    )
    return await iniciar_adicao(update, context)


async def comando_antigo_remover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await iniciar_remocao(update, context)


async def checar_agendado(app):
    logging.info("Executando checagem agendada...")
    await checar_precos(app)


def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_TOKEN não encontrado. Configure essa variável no Railway.")

    criar_tabela()

    app = ApplicationBuilder().token(TOKEN).build()

    conversa_adicionar = ConversationHandler(
        entry_points=[
            CommandHandler("adicionar", iniciar_adicao),
            MessageHandler(filters.Regex("^➕ Adicionar produto$"), iniciar_adicao)
        ],
        states={
            NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_nome)],
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_link)],
            PRECO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_preco)],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            MessageHandler(filters.Regex("^❌ Cancelar$"), cancelar)
        ]
    )

    conversa_remover = ConversationHandler(
        entry_points=[
            CommandHandler("remover", iniciar_remocao),
            MessageHandler(filters.Regex("^🗑 Remover produto$"), iniciar_remocao)
        ],
        states={
            REMOVER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_id_remocao)],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            MessageHandler(filters.Regex("^❌ Cancelar$"), cancelar)
        ]
    )

    app.add_handler(conversa_adicionar)
    app.add_handler(conversa_remover)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("listar", listar))
    app.add_handler(CommandHandler("checar", checar_manual))

    app.add_handler(MessageHandler(filters.Regex("^📦 Listar produtos$"), listar))
    app.add_handler(MessageHandler(filters.Regex("^🔎 Checar preços$"), checar_manual))

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