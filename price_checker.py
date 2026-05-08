from database import (
    buscar_produtos_ativos,
    atualizar_preco,
    marcar_alerta
)
from scrapers import buscar_preco


async def checar_precos(app):
    produtos = buscar_produtos_ativos()

    for produto in produtos:
        produto_id, chat_id, nome, url, preco_alvo, ultimo_preco, alerta_enviado = produto

        try:
            preco_atual = buscar_preco(url)

            if preco_atual is None:
                print(f"Não consegui encontrar preço para: {nome}")
                continue

            atualizar_preco(produto_id, preco_atual)

            if preco_atual <= preco_alvo and alerta_enviado == 0:
                mensagem = (
                    f"🔥 Preço abaixo do alvo!\n\n"
                    f"Produto: {nome}\n"
                    f"Preço alvo: R$ {preco_alvo:.2f}\n"
                    f"Preço atual: R$ {preco_atual:.2f}\n\n"
                    f"Link: {url}"
                )

                await app.bot.send_message(
                    chat_id=chat_id,
                    text=mensagem
                )

                marcar_alerta(produto_id, 1)

            elif preco_atual > preco_alvo:
                marcar_alerta(produto_id, 0)

        except Exception as erro:
            print(f"Erro ao checar produto {nome}: {erro}")
