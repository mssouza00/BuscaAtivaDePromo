import re
import logging
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.amazon.com.br/",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def limpar_url(url):
    if "amazon.com.br/dp/" in url:
        codigo = url.split("/dp/")[1].split("/")[0].split("?")[0]
        return f"https://www.amazon.com.br/dp/{codigo}"

    if "mercadolivre.com.br" in url and "?" in url:
        return url.split("?")[0]

    return url


def limpar_preco(texto):
    if not texto:
        return None

    texto = texto.replace("\xa0", " ")
    texto = texto.replace("R$", "")
    texto = texto.strip()

    match = re.search(r"[\d\.]+,\d{2}|[\d\.]+", texto)

    if not match:
        return None

    valor = match.group().replace(".", "").replace(",", ".")

    try:
        return float(valor)
    except Exception:
        return None


def buscar_preco_amazon(soup):
    """
    Busca o preço à vista na Amazon, priorizando os seletores
    do bloco principal de compra (corePriceDisplay).
    Evita capturar parcelas ou preços de produtos relacionados.
    """

    # 1ª tentativa: seletores do bloco de compra principal (mais confiável)
    seletores_prioritarios = [
        "#corePriceDisplay_desktop_feature_div span.a-price.apexPriceToPay",
        "#corePriceDisplay_desktop_feature_div span.a-price.priceToPay",
        "#corePrice_feature_div span.a-price.apexPriceToPay",
        "#corePrice_feature_div span.a-price.priceToPay",
        "#apex_desktop_newAccordionRow span.a-price.apexPriceToPay",
        "span.a-price.apexPriceToPay",
        "span.a-price.priceToPay",
    ]

    for seletor in seletores_prioritarios:
        elemento = soup.select_one(seletor)

        if not elemento:
            continue

        # Prefere .a-offscreen pois contém o valor completo formatado
        offscreen = elemento.select_one(".a-offscreen")
        if offscreen:
            preco = limpar_preco(offscreen.get_text(" ", strip=True))
            if preco and preco > 1:
                logging.info(f"Amazon preço encontrado via '{seletor}': R$ {preco}")
                return {
                    "preco": preco,
                    "origem": f"Amazon: {seletor}"
                }

        # Fallback: monta o preço a partir de .a-price-whole + .a-price-fraction
        whole = elemento.select_one(".a-price-whole")
        fraction = elemento.select_one(".a-price-fraction")

        if whole:
            texto = whole.get_text("", strip=True).rstrip(",").rstrip(".")
            if fraction:
                texto += "," + fraction.get_text("", strip=True)
            preco = limpar_preco(texto)
            if preco and preco > 1:
                logging.info(f"Amazon preço (whole/fraction) via '{seletor}': R$ {preco}")
                return {
                    "preco": preco,
                    "origem": f"Amazon: {seletor} (whole/fraction)"
                }

    # 2ª tentativa: buybox geral (menos confiável, mas ainda restrito ao bloco de compra)
    seletores_buybox = [
        "#desktop_buybox span.a-price",
        "#buybox span.a-price",
    ]

    for seletor in seletores_buybox:
        elemento = soup.select_one(seletor)

        if not elemento:
            continue

        offscreen = elemento.select_one(".a-offscreen")
        if offscreen:
            preco = limpar_preco(offscreen.get_text(" ", strip=True))
            if preco and preco > 1:
                logging.warning(
                    f"Amazon: usando seletor de fallback '{seletor}'. "
                    f"Preço capturado: R$ {preco}. Verifique se é o preço à vista."
                )
                return {
                    "preco": preco,
                    "origem": f"Amazon (fallback): {seletor} — verifique se é o preço à vista"
                }

    # Nenhum seletor funcionou — NÃO faz fallback por texto para evitar pegar parcelas
    logging.warning("Amazon: nenhum seletor de preço funcionou. Possível mudança no HTML ou CAPTCHA.")
    return None


def buscar_preco_mercado_livre(soup):
    """
    Busca o preço no Mercado Livre priorizando o bloco principal de preço.
    """

    seletores = [
        ".ui-pdp-price__second-line .andes-money-amount",
        ".ui-pdp-price .andes-money-amount",
        ".ui-pdp-container__row--price .andes-money-amount",
        ".andes-money-amount",
    ]

    for seletor in seletores:
        bloco = soup.select_one(seletor)

        if not bloco:
            continue

        fraction = bloco.select_one(".andes-money-amount__fraction")
        cents = bloco.select_one(".andes-money-amount__cents")

        if fraction:
            texto = fraction.get_text("", strip=True)

            if cents:
                texto += "," + cents.get_text("", strip=True)

            preco = limpar_preco(texto)

            if preco and preco > 1:
                logging.info(f"Mercado Livre preço encontrado via '{seletor}': R$ {preco}")
                return {
                    "preco": preco,
                    "origem": f"Mercado Livre: {seletor}"
                }

    # Fallback por texto apenas se nenhum seletor funcionou
    # Pega o primeiro valor válido encontrado (mais conservador que o anterior)
    texto = soup.get_text(" ")
    valores = re.findall(r"R\$\s?[\d\.]+,\d{2}", texto)

    for valor in valores:
        preco = limpar_preco(valor)
        if preco and preco > 1:
            logging.warning(
                f"Mercado Livre: usando fallback de texto. "
                f"Preço capturado: R$ {preco}. Pode não ser o preço correto."
            )
            return {
                "preco": preco,
                "origem": "Mercado Livre (fallback texto) — verifique se é o preço correto"
            }

    return None


def buscar_preco_detalhado(url):
    url = limpar_url(url)

    logging.info(f"Consultando URL: {url}")

    try:
        session = requests.Session()

        response = session.get(
            url,
            headers=HEADERS,
            timeout=10,
            cookies={
                "i18n-prefs": "BRL",
                "lc-acbpt": "pt_BR"
            }
        )

        if response.status_code != 200:
            logging.error(f"Erro HTTP {response.status_code} para URL: {url}")
            return {
                "preco": None,
                "origem": f"Erro HTTP {response.status_code}"
            }

        html_lower = response.text.lower()

        if "captcha" in html_lower or "digite os caracteres" in html_lower:
            logging.warning(f"CAPTCHA detectado para URL: {url}")
            return {
                "preco": None,
                "origem": "Site retornou captcha/bloqueio"
            }

        soup = BeautifulSoup(response.text, "html.parser")

        if "amazon.com" in url:
            resultado = buscar_preco_amazon(soup)
            if resultado:
                logging.info(f"Resultado Amazon — Preço: R$ {resultado['preco']} | Origem: {resultado['origem']}")
                return resultado

        if "mercadolivre.com" in url:
            resultado = buscar_preco_mercado_livre(soup)
            if resultado:
                logging.info(f"Resultado ML — Preço: R$ {resultado['preco']} | Origem: {resultado['origem']}")
                return resultado

        logging.warning(f"Preço não encontrado para URL: {url}")
        return {
            "preco": None,
            "origem": "Preço não encontrado no HTML recebido"
        }

    except Exception as erro:
        logging.error(f"Erro no scraper para {url}: {erro}")
        return {
            "preco": None,
            "origem": f"Erro no scraper: {erro}"
        }


def buscar_preco(url):
    resultado = buscar_preco_detalhado(url)

    if resultado and resultado.get("preco"):
        return resultado["preco"]

    return None