import os
import json
import time
import logging
import requests
import re
import schedule
import threading
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN", "8554823712:AAGUFJPwjzVIOwrCTF9qV5pDbm4FivFxXrQ")
DATA_FILE = "produtos.json"

AGUARDANDO_URL, AGUARDANDO_PRECO = range(2)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}


# ---------- Persistência ----------

def carregar_dados():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_dados(dados):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


# ---------- Scraping ----------

def limpar_preco(texto):
    """Extrai número float de string de preço."""
    texto = texto.replace(".", "").replace(",", ".")
    nums = re.findall(r"\d+\.?\d*", texto)
    return float(nums[0]) if nums else None


def buscar_preco_amazon(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        # Tenta seletores comuns da Amazon BR
        seletores = [
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            ".a-price .a-offscreen",
            "#price_inside_buybox",
            "#corePrice_feature_div .a-price .a-offscreen",
        ]
        for sel in seletores:
            el = soup.select_one(sel)
            if el:
                preco = limpar_preco(el.get_text())
                if preco:
                    return preco

        # Título do produto
        titulo = soup.select_one("#productTitle")
        nome = titulo.get_text(strip=True)[:60] if titulo else "Produto Amazon"
        return None, nome
    except Exception as e:
        logger.error(f"Erro Amazon: {e}")
        return None


def buscar_preco_mercadolivre(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        seletores = [
            ".andes-money-amount__fraction",
            ".price-tag-fraction",
            ".ui-pdp-price__second-line .andes-money-amount__fraction",
        ]
        for sel in seletores:
            el = soup.select_one(sel)
            if el:
                preco = limpar_preco(el.get_text())
                if preco:
                    return preco
        return None
    except Exception as e:
        logger.error(f"Erro ML: {e}")
        return None


def buscar_nome_produto(url, soup):
    try:
        if "amazon" in url:
            el = soup.select_one("#productTitle")
        else:
            el = soup.select_one(".ui-pdp-title") or soup.select_one("h1")
        return el.get_text(strip=True)[:60] if el else url[:40]
    except:
        return url[:40]


def obter_info_produto(url):
    """Retorna (preco_float, nome_str) ou (None, None) em caso de erro."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        nome = buscar_nome_produto(url, soup)

        if "amazon.com.br" in url or "amazon.com" in url:
            seletores = [
                "#priceblock_ourprice",
                "#priceblock_dealprice",
                ".a-price .a-offscreen",
                "#price_inside_buybox",
                "#corePrice_feature_div .a-price .a-offscreen",
            ]
        elif "mercadolivre" in url or "mercadolibre" in url:
            seletores = [
                ".andes-money-amount__fraction",
                ".price-tag-fraction",
                ".ui-pdp-price__second-line .andes-money-amount__fraction",
            ]
        else:
            return None, "Site não suportado"

        for sel in seletores:
            el = soup.select_one(sel)
            if el:
                preco = limpar_preco(el.get_text())
                if preco:
                    return preco, nome

        return None, nome
    except Exception as e:
        logger.error(f"Erro ao buscar produto: {e}")
        return None, None


# ---------- Handlers do Bot ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Sou seu *Bot de Alertas de Preço*!\n\n"
        "📋 *Comandos disponíveis:*\n"
        "• /adicionar — Adicionar produto para monitorar\n"
        "• /listar — Ver produtos monitorados\n"
        "• /remover — Remover um produto\n"
        "• /verificar — Checar preços agora\n"
        "• /ajuda — Instruções de uso\n\n"
        "Suporte: 🛒 Amazon BR e 🟡 Mercado Livre",
        parse_mode="Markdown"
    )


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Como usar:*\n\n"
        "1️⃣ Use /adicionar e cole o link do produto\n"
        "2️⃣ Informe o preço-alvo (ex: `1500.00`)\n"
        "3️⃣ Quando o preço baixar, você recebe um alerta!\n\n"
        "⏰ Verificação automática a cada *1 hora*\n\n"
        "⚠️ *Dica:* Prefira links diretos do produto, não de buscas.",
        parse_mode="Markdown"
    )


async def adicionar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔗 Cole o *link do produto* que deseja monitorar:\n"
        "(Amazon BR ou Mercado Livre)",
        parse_mode="Markdown"
    )
    return AGUARDANDO_URL


async def receber_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "amazon.com" not in url and "mercadolivre" not in url and "mercadolibre" not in url:
        await update.message.reply_text(
            "❌ Link não reconhecido. Por favor, use links da *Amazon BR* ou *Mercado Livre*.",
            parse_mode="Markdown"
        )
        return AGUARDANDO_URL

    context.user_data["url"] = url
    msg = await update.message.reply_text("🔍 Buscando informações do produto...")

    preco, nome = obter_info_produto(url)

    if preco:
        context.user_data["nome"] = nome
        context.user_data["preco_atual"] = preco
        await msg.edit_text(
            f"✅ Produto encontrado!\n\n"
            f"📦 *{nome}*\n"
            f"💰 Preço atual: *R$ {preco:,.2f}*\n\n"
            f"Digite o *preço-alvo* para ser alertado (ex: `{preco * 0.9:.2f}`):",
            parse_mode="Markdown"
        )
    else:
        context.user_data["nome"] = "Produto"
        context.user_data["preco_atual"] = None
        await msg.edit_text(
            "⚠️ Não consegui ler o preço agora (pode ser proteção do site).\n"
            "Digite mesmo assim o *preço-alvo* desejado (ex: `1500.00`):",
            parse_mode="Markdown"
        )

    return AGUARDANDO_PRECO


async def receber_preco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().replace(",", ".")
    try:
        preco_alvo = float(re.sub(r"[^\d.]", "", texto))
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Digite só o número, ex: `1500.00`", parse_mode="Markdown")
        return AGUARDANDO_PRECO

    url = context.user_data["url"]
    nome = context.user_data.get("nome", "Produto")
    preco_atual = context.user_data.get("preco_atual")
    user_id = str(update.effective_user.id)

    dados = carregar_dados()
    if user_id not in dados:
        dados[user_id] = []

    produto_id = str(int(time.time()))
    dados[user_id].append({
        "id": produto_id,
        "url": url,
        "nome": nome,
        "preco_alvo": preco_alvo,
        "preco_atual": preco_atual,
        "adicionado_em": datetime.now().isoformat()
    })
    salvar_dados(dados)

    preco_str = f"R$ {preco_atual:,.2f}" if preco_atual else "não detectado"
    await update.message.reply_text(
        f"✅ *Produto adicionado com sucesso!*\n\n"
        f"📦 {nome}\n"
        f"💰 Preço atual: {preco_str}\n"
        f"🎯 Seu alerta: *R$ {preco_alvo:,.2f}*\n\n"
        f"Você será notificado assim que o preço baixar!",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operação cancelada.")
    return ConversationHandler.END


async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    dados = carregar_dados()
    produtos = dados.get(user_id, [])

    if not produtos:
        await update.message.reply_text("📭 Você não tem produtos monitorados.\nUse /adicionar para começar!")
        return

    texto = "📋 *Seus produtos monitorados:*\n\n"
    for i, p in enumerate(produtos, 1):
        preco_str = f"R$ {p['preco_atual']:,.2f}" if p.get("preco_atual") else "—"
        texto += (
            f"*{i}. {p['nome']}*\n"
            f"   💰 Atual: {preco_str}\n"
            f"   🎯 Alerta: R$ {p['preco_alvo']:,.2f}\n\n"
        )

    await update.message.reply_text(texto, parse_mode="Markdown")


async def remover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    dados = carregar_dados()
    produtos = dados.get(user_id, [])

    if not produtos:
        await update.message.reply_text("📭 Você não tem produtos monitorados.")
        return

    botoes = []
    for p in produtos:
        botoes.append([InlineKeyboardButton(f"❌ {p['nome'][:40]}", callback_data=f"rem_{p['id']}")])

    await update.message.reply_text(
        "Selecione o produto para remover:",
        reply_markup=InlineKeyboardMarkup(botoes)
    )


async def callback_remover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    produto_id = query.data.replace("rem_", "")
    user_id = str(query.from_user.id)
    dados = carregar_dados()

    antes = len(dados.get(user_id, []))
    dados[user_id] = [p for p in dados.get(user_id, []) if p["id"] != produto_id]
    depois = len(dados[user_id])
    salvar_dados(dados)

    if antes > depois:
        await query.edit_message_text("✅ Produto removido com sucesso!")
    else:
        await query.edit_message_text("⚠️ Produto não encontrado.")


async def verificar_agora(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    dados = carregar_dados()
    produtos = dados.get(user_id, [])

    if not produtos:
        await update.message.reply_text("📭 Você não tem produtos monitorados.")
        return

    msg = await update.message.reply_text("🔍 Verificando preços, aguarde...")
    resultado = []

    for p in produtos:
        preco, _ = obter_info_produto(p["url"])
        if preco:
            p["preco_atual"] = preco
            status = "🟢 Abaixo do alerta!" if preco <= p["preco_alvo"] else "🔴 Acima do alerta"
            resultado.append(f"📦 *{p['nome']}*\n   💰 R$ {preco:,.2f} | 🎯 R$ {p['preco_alvo']:,.2f} | {status}")
        else:
            resultado.append(f"📦 *{p['nome']}*\n   ⚠️ Não foi possível ler o preço agora")

    salvar_dados(dados)
    await msg.edit_text(
        "📊 *Resultado da verificação:*\n\n" + "\n\n".join(resultado),
        parse_mode="Markdown"
    )


# ---------- Loop de verificação automática ----------

def verificar_alertas(app):
    dados = carregar_dados()
    for user_id, produtos in dados.items():
        for p in produtos:
            try:
                preco, _ = obter_info_produto(p["url"])
                if preco:
                    p["preco_atual"] = preco
                    if preco <= p["preco_alvo"]:
                        mensagem = (
                            f"🚨 *ALERTA DE PREÇO!*\n\n"
                            f"📦 *{p['nome']}*\n"
                            f"💰 Preço atual: *R$ {preco:,.2f}*\n"
                            f"🎯 Seu alerta: R$ {p['preco_alvo']:,.2f}\n\n"
                            f"[🛒 Ver produto]({p['url']})"
                        )
                        import asyncio
                        asyncio.run(
                            app.bot.send_message(
                                chat_id=int(user_id),
                                text=mensagem,
                                parse_mode="Markdown",
                                disable_web_page_preview=False
                            )
                        )
            except Exception as e:
                logger.error(f"Erro ao verificar {p['url']}: {e}")
    salvar_dados(dados)


def iniciar_scheduler(app):
    schedule.every(1).hours.do(verificar_alertas, app)

    def loop():
        while True:
            schedule.run_pending()
            time.sleep(60)

    t = threading.Thread(target=loop, daemon=True)
    t.start()


# ---------- Main ----------

def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("adicionar", adicionar_inicio)],
        states={
            AGUARDANDO_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_url)],
            AGUARDANDO_PRECO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_preco)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(conv)
    app.add_handler(CommandHandler("listar", listar))
    app.add_handler(CommandHandler("remover", remover))
    app.add_handler(CommandHandler("verificar", verificar_agora))
    app.add_handler(CallbackQueryHandler(callback_remover, pattern="^rem_"))

    iniciar_scheduler(app)

    print("🤖 Bot iniciado! Pressione Ctrl+C para parar.")
    app.run_polling()


if __name__ == "__main__":
    main()
