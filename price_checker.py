import asyncio

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
                timeout=10
            )

            if resultado_preco is None:
                resultados.append(
                    f"⚠️ {nome}\n"
                    f"Não consegui encontrar o preço."
                )
                continue

            preco_atual = resultado_preco["preco"]
            origem = resultado_preco["origem"]

            atualizar_preco(produto_id, preco_atual)
            salvar_historico_preco(produto_id, preco_atual)

            if preco_atual <= preco_alvo:
                mensagem = (
                    f"🔥 {nome}\n"
                    f"Preço atual: R$ {preco_atual:.2f}\n"
                    f"Preço alvo: R$ {preco_alvo:.2f}\n"
                    f"✅ Está abaixo ou igual ao alvo!\n\n"
                    f"Origem do preço: {origem}\n"
                    f"{url}"
                )

                if alerta_enviado == 0:
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=mensagem
                    )

                marcar_alerta(produto_id, 1)

            else:
                diferenca = preco_atual - preco_alvo

                mensagem = (
                    f"📦 {nome}\n"
                    f"Preço atual: R$ {preco_atual:.2f}\n"
                    f"Preço alvo: R$ {preco_alvo:.2f}\n"
                    f"❌ R$ {diferenca:.2f} acima do alvo.\n\n"
                    f"Origem do preço: {origem}"
                )

                marcar_alerta(produto_id, 0)

            resultados.append(mensagem)

        except asyncio.TimeoutError:
            resultados.append(
                f"⏱ {nome}\n"
                f"Tempo esgotado ao consultar o site."
            )

        except Exception as erro:
            resultados.append(
                f"❌ {nome}\n"
                f"Erro: {erro}"
            )

    return resultados
    return resultados