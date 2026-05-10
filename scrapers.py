def buscar_preco_amazon(soup):
    # 1. Tenta pegar o preço principal exibido na caixa lateral / compra
    seletores_blocos = [
        "#corePrice_feature_div",
        "#corePriceDisplay_desktop_feature_div",
        "#apex_desktop",
        "#desktop_buybox",
        "#buybox",
    ]

    for seletor_bloco in seletores_blocos:
        bloco = soup.select_one(seletor_bloco)

        if not bloco:
            continue

        whole = bloco.select_one(".a-price-whole")
        fraction = bloco.select_one(".a-price-fraction")

        if whole:
            texto = whole.get_text(strip=True)

            if fraction:
                texto += "," + fraction.get_text(strip=True)

            preco = limpar_preco(texto)

            if preco:
                return {
                    "preco": preco,
                    "origem": f"Amazon: preço principal em {seletor_bloco}"
                }

    # 2. Tenta pegar preços visíveis do bloco principal
    seletores_prioritarios = [
        "#corePrice_feature_div .a-price.aok-align-center .a-offscreen",
        "#corePrice_feature_div .priceToPay .a-offscreen",
        "#corePrice_feature_div .a-price .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-offscreen",
        "#apex_desktop .a-price .a-offscreen",
        "#desktop_buybox .a-price .a-offscreen",
    ]

    for seletor in seletores_prioritarios:
        elemento = soup.select_one(seletor)

        if elemento:
            preco = limpar_preco(elemento.get_text(" "))

            if preco:
                return {
                    "preco": preco,
                    "origem": f"Amazon: {seletor}"
                }

    # 3. Último recurso: ignora textos de parcela e preço antigo
    textos_invalidos = [
        "de:",
        "preço anterior",
        "economize",
        "cupom",
        "parcela",
        "parcelas",
        "sem juros",
        "mês",
        "/mês"
    ]

    candidatos = soup.select("span.a-offscreen")

    for elemento in candidatos:
        texto = elemento.get_text(" ").strip()
        texto_lower = texto.lower()

        if any(invalido in texto_lower for invalido in textos_invalidos):
            continue

        preco = limpar_preco(texto)

        if preco:
            return {
                "preco": preco,
                "origem": "Amazon: span.a-offscreen filtrado"
            }

    return None