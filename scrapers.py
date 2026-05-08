import re
import json
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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
    texto = texto.replace("R$", "").strip()

    match = re.search(r"[\d\.]+,\d{2}|[\d\.]+", texto)

    if not match:
        return None

    valor = match.group().replace(".", "").replace(",", ".")

    try:
        return float(valor)
    except ValueError:
        return None


def buscar_preco_meta(soup):
    metas = [
        {"property": "product:price:amount"},
        {"property": "og:price:amount"},
        {"name": "twitter:data1"},
        {"itemprop": "price"},
    ]

    for meta in metas:
        elemento = soup.find("meta", meta)

        if elemento:
            conteudo = elemento.get("content")
            preco = limpar_preco(conteudo)

            if preco:
                return preco

    return None


def buscar_preco_json(soup):
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        try:
            if not script.string:
                continue

            dados = json.loads(script.string)

            if isinstance(dados, list):
                itens = dados
            else:
                itens = [dados]

            for item in itens:
                if not isinstance(item, dict):
                    continue

                offers = item.get("offers")

                if isinstance(offers, dict):
                    price = offers.get("price")

                    if price:
                        return float(str(price).replace(",", "."))

                if isinstance(offers, list):
                    for offer in offers:
                        price = offer.get("price")
                        if price:
                            return float(str(price).replace(",", "."))

        except Exception:
            continue

    return None


def buscar_preco_mercado_livre(soup):
    seletores = [
        ".ui-pdp-price__second-line .andes-money-amount__fraction",
        ".ui-pdp-price__second-line .andes-money-amount",
        ".andes-money-amount__fraction",
        ".price-tag-fraction",
        ".poly-price__current .andes-money-amount__fraction",
    ]

    for seletor in seletores:
        elemento = soup.select_one(seletor)

        if elemento:
            preco = limpar_preco(elemento.get_text(" "))
            if preco:
                return preco

    texto = soup.get_text(" ")

    match = re.search(r"R\$\s?[\d\.]+,\d{2}", texto)
    if match:
        return limpar_preco(match.group())

    match = re.search(r"R\$\s?[\d\.]+", texto)
    if match:
        return limpar_preco(match.group())

    return None


def buscar_preco_amazon(soup):
    seletores = [
        "#corePrice_feature_div .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-offscreen",
        ".apexPriceToPay .a-offscreen",
        ".a-price .a-offscreen",
        "span.a-price span.a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "#priceblock_saleprice",
        "span.a-offscreen",
    ]

    for seletor in seletores:
        elemento = soup.select_one(seletor)

        if elemento:
            preco = limpar_preco(elemento.get_text(" "))
            if preco:
                return preco

    texto = soup.get_text(" ")

    match = re.search(r"R\$\s?[\d\.]+,\d{2}", texto)
    if match:
        return limpar_preco(match.group())

    return None


def buscar_preco_generico(soup):
    texto = soup.get_text(" ")

    match = re.search(r"R\$\s?[\d\.]+,\d{2}", texto)

    if match:
        return limpar_preco(match.group())

    return None


def buscar_preco(url):
    url = limpar_url(url)

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=8
        )

        if response.status_code != 200:
            print(f"Erro HTTP {response.status_code} ao acessar {url}")
            return None

        html_lower = response.text.lower()

        if "captcha" in html_lower or "digite os caracteres" in html_lower:
            print("Site retornou captcha/bloqueio.")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        preco_meta = buscar_preco_meta(soup)
        if preco_meta:
            return preco_meta

        preco_json = buscar_preco_json(soup)
        if preco_json:
            return preco_json

        if "mercadolivre.com" in url:
            preco_ml = buscar_preco_mercado_livre(soup)
            if preco_ml:
                return preco_ml

        if "amazon.com" in url:
            preco_amazon = buscar_preco_amazon(soup)
            if preco_amazon:
                return preco_amazon

        preco_generico = buscar_preco_generico(soup)
        if preco_generico:
            return preco_generico

        print("Preço não encontrado.")
        return None

    except Exception as erro:
        print(f"Erro no scraper: {erro}")
        return None