import asyncio
import logging

from database import (
    buscar_produtos_ativos,
    atualizar_preco,
    marcar_alerta,
    salvar_historico_preco
)
from scrapers import buscar_preco_detalhado


async def checar_precos(app, chat_id_manual=None):
    produtos = buscar_produtos_ativos()
    resultados = []

    for produto in produtos:
        produto_id, chat_id, nome, url, preco_alvo, ultimo_preco, alerta_enviado = produto

        if chat_id_manual is not None and chat_id != chat_id_manual:
            continue

        try:
            resultado_preco = await asyncio.wait_for(
                asyncio.to_thread(buscar_preco_detalhado, url),
                timeout=15
            )

            if resultado_preco is None or resultado_preco.get("preco") is None:
                origem_erro = resultado_preco.get("origem", "motivo desconhecido") if resultado_preco else "motivo desconhecido"
                logging.warning(f"Preço não encontrado para '{nome}': {origem_erro}")
                resultados.append(
                    f"⚠️ {nome}\n"
                    f"Não consegui encontrar o preço.\n"
                    f"Motivo: {origem_erro}"
                )
                continue

            preco_atual = resultado_preco["preco"]
            origem = resultado_preco["origem"]

            logging.info(f"Produto '{nome}' — Preço: R$ {preco_atual:.2f} | Origem: {origem}")

            atualizar_preco(produto_id, preco_atual)
            salvar_historico_preco(produto_id, preco_atual)

            if preco_atual <= preco_alvo:
                mensagem = (
                    f"🔥 {nome}\n"
                    f"Preço atual: R$ {preco_atual:.2f}\n"
                    f"Preço alvo: R$ {preco_alvo:.2f}\n"
                    f"✅ Está abaixo ou igual ao alvo!\n\n"
                    f"⚙️ Capturado via: {origem}\n"
                    f"🔗 {url}"
                )

                if alerta_enviado == 0:
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=mensagem
                    )
                    logging.info(f"Alerta enviado para chat_id {chat_id} — produto '{nome}'")

                marcar_alerta(produto_id, 1)

            else:
                diferenca = preco_atual - preco_alvo

                mensagem = (
                    f"📦 {nome}\n"
                    f"Preço atual: R$ {preco_atual:.2f}\n"
                    f"Preço alvo: R$ {preco_alvo:.2f}\n"
                    f"❌ R$ {diferenca:.2f} acima do alvo.\n\n"
                    f"⚙️ Capturado via: {origem}"
                )

                marcar_alerta(produto_id, 0)

            resultados.append(mensagem)

        except asyncio.TimeoutError:
            logging.warning(f"Timeout ao consultar '{nome}'")
            resultados.append(
                f"⏱ {nome}\n"
                f"Tempo esgotado ao consultar o site."
            )

        except Exception as erro:
            logging.error(f"Erro ao checar '{nome}': {erro}")
            resultados.append(
                f"❌ {nome}\n"
                f"Erro: {erro}"
            )

    return resultados