import re
import json
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
    seletores = [
        "span.a-price.apexPriceToPay",
        "span.a-price.priceToPay",
        "span.a-price[data-a-color='priceToPay']",
        "#corePriceDisplay_desktop_feature_div span.a-price",
        "#corePrice_feature_div span.a-price",
        "#apex_desktop span.a-price",
        "#desktop_buybox span.a-price",
        "#buybox span.a-price",
        "span.a-price",
    ]

    candidatos = []

    for seletor in seletores:
        elementos = soup.select(seletor)

        for elemento in elementos:
            whole = elemento.select_one(".a-price-whole")
            fraction = elemento.select_one(".a-price-fraction")

            if whole:
                texto = whole.get_text("", strip=True)

                if fraction:
                    texto += "," + fraction.get_text("", strip=True)

                preco = limpar_preco(texto)

                if preco and preco > 100:
                    candidatos.append((preco, seletor))

            offscreen = elemento.select_one(".a-offscreen")

            if offscreen:
                preco = limpar_preco(offscreen.get_text(" ", strip=True))

                if preco and preco > 100:
                    candidatos.append((preco, seletor + " .a-offscreen"))

    if candidatos:
        menor = min(candidatos, key=lambda x: x[0])
        return {
            "preco": menor[0],
            "origem": f"Amazon: {menor[1]}"
        }

    texto = soup.get_text(" ")
    valores = re.findall(r"R\$\s?[\d\.]+,\d{2}", texto)

    candidatos_texto = []

    for valor in valores:
        preco = limpar_preco(valor)

        if preco and preco > 500:
            candidatos_texto.append(preco)

    if candidatos_texto:
        return {
            "preco": min(candidatos_texto),
            "origem": "Amazon: menor preço no texto"
        }

    return None


def buscar_preco_mercado_livre(soup):
    seletores = [
        ".ui-pdp-price__second-line",
        ".ui-pdp-price",
        ".ui-pdp-container__row--price",
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

            if preco:
                return {
                    "preco": preco,
                    "origem": f"Mercado Livre: {seletor}"
                }

    texto = soup.get_text(" ")
    valores = re.findall(r"R\$\s?[\d\.]+,\d{2}|R\$\s?[\d\.]+", texto)

    for valor in valores:
        preco = limpar_preco(valor)

        if preco and preco > 10:
            return {
                "preco": preco,
                "origem": "Mercado Livre: texto da página"
            }

    return None


def buscar_preco_detalhado(url):
    url = limpar_url(url)

    try:
        session = requests.Session()

        response = session.get(
            url,
            headers=HEADERS,
            timeout=7,
            cookies={
                "i18n-prefs": "BRL",
                "lc-acbpt": "pt_BR"
            }
        )

        if response.status_code != 200:
            return {
                "preco": None,
                "origem": f"Erro HTTP {response.status_code}"
            }

        html_lower = response.text.lower()

        if "captcha" in html_lower or "digite os caracteres" in html_lower:
            return {
                "preco": None,
                "origem": "Site retornou captcha/bloqueio"
            }

        soup = BeautifulSoup(response.text, "html.parser")

        if "amazon.com" in url:
            resultado = buscar_preco_amazon(soup)
            if resultado:
                return resultado

        if "mercadolivre.com" in url:
            resultado = buscar_preco_mercado_livre(soup)
            if resultado:
                return resultado

        return {
            "preco": None,
            "origem": "Preço não encontrado no HTML recebido pelo Railway"
        }

    except Exception as erro:
        return {
            "preco": None,
            "origem": f"Erro no scraper: {erro}"
        }


def buscar_preco(url):
    resultado = buscar_preco_detalhado(url)

    if resultado and resultado.get("preco"):
        return resultado["preco"]

    return None