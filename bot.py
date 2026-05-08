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
    remover_produto,
    buscar_historico_produto,
    buscar_resumo_historico
)

from price_checker import checar_precos


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", 60))

NOME, LINK, PRECO, REMOVER_ID, HISTORICO_ID = range(5)


def menu_principal():
    teclado = [
        ["➕ Adicionar produto", "📦 Listar produtos"],
        ["🔎 Checar preços", "📈 Histórico"],
        ["🗑 Remover produto"]
    ]

    return ReplyKeyboardMarkup(
        teclado,
        resize_keyboard=True
    )


def menu_cancelar():
    return ReplyKeyboardMarkup(
        [["❌ Cancelar"]],
        resize_keyboard=True
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = """
Olá! Eu sou seu bot de monitoramento de preços.

Funções disponíveis:

➕ Adicionar produto
📦 Listar produtos
🔎 Checar preços
📈 Histórico
🗑 Remover produto
"""

    await update.message.reply_text(
        mensagem,
        reply_markup=menu_principal()
    )


async def iniciar_adicao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "➕ Qual o nome do produto?",
        reply_markup=menu_cancelar()
    )

    return NOME


async def receber_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()

    if nome == "❌ Cancelar":
        return await cancelar(update, context)

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
            "Link inválido."
        )
        return LINK

    context.user_data["url"] = url

    await update.message.reply_text(
        "Agora envie o preço alvo.\n\nExemplo: 2500"
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

        chat_id = update.message.chat_id

        adicionar_produto(
            chat_id,
            context.user_data["nome"],
            context.user_data["url"],
            preco
        )

        await update.message.reply_text(
            f"✅ Produto cadastrado!\n\n"
            f"Nome: {context.user_data['nome']}\n"
            f"Preço alvo: R$ {preco:.2f}",
            reply_markup=menu_principal()
        )

        context.user_data.clear()

        return ConversationHandler.END

    except Exception:
        await update.message.reply_text(
            "Preço inválido.\nExemplo: 2500"
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

        mensagem += (
            f"ID: {produto_id}\n"
            f"{nome}\n"
            f"Alvo: R$ {preco_alvo:.2f}\n"
            f"Último: {ultimo}\n\n"
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
            "Você ainda não tem produtos.",
            reply_markup=menu_principal()
        )
        return ConversationHandler.END

    mensagem = "🗑 Envie o ID do produto:\n\n"

    for produto in produtos:
        produto_id, nome, *_ = produto
        mensagem += f"{produto_id} - {nome}\n"

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

        remover_produto(update.message.chat_id, produto_id)

        await update.message.reply_text(
            "✅ Produto removido.",
            reply_markup=menu_principal()
        )

        return ConversationHandler.END

    except Exception:
        await update.message.reply_text(
            "ID inválido."
        )
        return REMOVER_ID


async def iniciar_historico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    produtos = listar_produtos(chat_id)

    if not produtos:
        await update.message.reply_text(
            "Você ainda não cadastrou produtos.",
            reply_markup=menu_principal()
        )
        return ConversationHandler.END

    mensagem = "📈 Envie o ID do produto:\n\n"

    for produto in produtos:
        produto_id, nome, *_ = produto
        mensagem += f"{produto_id} - {nome}\n"

    await update.message.reply_text(
        mensagem,
        reply_markup=menu_cancelar()
    )

    return HISTORICO_ID


async def receber_id_historico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()

    if texto == "❌ Cancelar":
        return await cancelar(update, context)

    try:
        produto_id = int(texto)

        resumo = buscar_resumo_historico(
            update.message.chat_id,
            produto_id
        )

        historico = buscar_historico_produto(
            update.message.chat_id,
            produto_id,
            limite=10
        )

        if not resumo or not historico:
            await update.message.reply_text(
                "Ainda não existe histórico.",
                reply_markup=menu_principal()
            )

            return ConversationHandler.END

        nome, menor, maior, medio, total = resumo

        mensagem = (
            f"📈 {nome}\n\n"
            f"Menor: R$ {menor:.2f}\n"
            f"Maior: R$ {maior:.2f}\n"
            f"Médio: R$ {medio:.2f}\n\n"
        )

        for item in historico:
            _, preco, data_hora = item
            mensagem += f"{data_hora} → R$ {preco:.2f}\n"

        await update.message.reply_text(
            mensagem,
            reply_markup=menu_principal()
        )

        return ConversationHandler.END

    except Exception:
        await update.message.reply_text(
            "ID inválido."
        )

        return HISTORICO_ID


async def checar_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resultados = await checar_precos(
        context.application,
        chat_id_manual=update.message.chat_id
    )

    if not resultados:
        await update.message.reply_text(
            "Nenhum produto encontrado.",
            reply_markup=menu_principal()
        )
        return

    mensagem = "🔎 Resultado:\n\n"
    mensagem += "\n\n".join(resultados)

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


async def checar_agendado(app):
    logging.info("Executando checagem automática...")
    await checar_precos(app)


def main():
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

    conversa_historico = ConversationHandler(
        entry_points=[
            CommandHandler("historico", iniciar_historico),
            MessageHandler(filters.Regex("^📈 Histórico$"), iniciar_historico)
        ],
        states={
            HISTORICO_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_id_historico)],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            MessageHandler(filters.Regex("^❌ Cancelar$"), cancelar)
        ]
    )

    app.add_handler(conversa_adicionar)
    app.add_handler(conversa_remover)
    app.add_handler(conversa_historico)

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

    logging.info("Bot iniciado...")

    app.run_polling()


if __name__ == "__main__":
    main()