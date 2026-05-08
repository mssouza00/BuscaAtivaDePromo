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


def limpar_url_amazon(url):
    if "amazon.com.br/dp/" in url:
        codigo = url.split("/dp/")[1].split("/")[0].split("?")[0]
        return f"https://www.amazon.com.br/dp/{codigo}"

    return url


def limpar_preco(texto):
    if not texto:
        return None

    texto = texto.replace("\xa0", " ").replace("R$", "").strip()

    match = re.search(r"[\d\.]+,\d{2}", texto)

    if not match:
        return None

    valor = match.group().replace(".", "").replace(",", ".")

    try:
        return float(valor)
    except ValueError:
        return None


def buscar_preco_json(soup):
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        try:
            dados = json.loads(script.string)

            if isinstance(dados, dict):
                offers = dados.get("offers")

                if isinstance(offers, dict):
                    price = offers.get("price")

                    if price:
                        return float(str(price).replace(",", "."))

        except Exception:
            continue

    return None


def buscar_preco_html(soup):
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


def buscar_preco(url):
    url = limpar_url_amazon(url)

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=5
        )

        if response.status_code != 200:
            print(f"Erro HTTP {response.status_code} ao acessar {url}")
            return None

        html = response.text

        if "captcha" in html.lower() or "digite os caracteres" in html.lower():
            print("Amazon retornou captcha/bloqueio.")
            return None

        soup = BeautifulSoup(html, "html.parser")

        preco_json = buscar_preco_json(soup)
        if preco_json:
            return preco_json

        preco_html = buscar_preco_html(soup)
        if preco_html:
            return preco_html

        print("Preço não encontrado no HTML.")
        return None

    except Exception as erro:
        print(f"Erro no scraper: {erro}")
        return None