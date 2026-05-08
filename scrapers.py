import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus


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


def buscar_preco_mercado_livre(soup):
    seletores = [
        ".ui-pdp-price__second-line .andes-money-amount",
        ".ui-pdp-price__second-line .andes-money-amount__fraction",
        ".ui-pdp-price__second-line",
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

    texto_pagina = soup.get_text(" ")

    match = re.search(r"R\$\s?[\d\.]+,\d{2}", texto_pagina)
    if match:
        return limpar_preco(match.group())

    match = re.search(r"R\$\s?[\d\.]+", texto_pagina)
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
    seletores = [
        ".price",
        ".product-price",
        ".sale-price",
        ".current-price",
        "[data-testid='price']"
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

        html_lower = response.text.lower()

        if "captcha" in html_lower or "digite os caracteres" in html_lower:
            print("Site retornou captcha/bloqueio.")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        preco_json = buscar_preco_json(soup)
        if preco_json:
            return preco_json

        if "mercadolivre.com" in url or "mercadolivre.com.br" in url:
            preco_ml = buscar_preco_mercado_livre(soup)
            if preco_ml:
                return preco_ml

        if "amazon.com.br" in url or "amazon.com" in url:
            preco_amazon = buscar_preco_amazon(soup)
            if preco_amazon:
                return preco_amazon

        preco_generico = buscar_preco_generico(soup)
        if preco_generico:
            return preco_generico

        print("Preço não encontrado no HTML.")
        return None

    except Exception as erro:
        print(f"Erro no scraper: {erro}")
        return None


def buscar_produtos_mercado_livre(termo, limite=5):
    termo_url = quote_plus(termo)
    url_busca = f"https://lista.mercadolivre.com.br/{termo_url}"

    try:
        response = requests.get(
            url_busca,
            headers=HEADERS,
            timeout=8
        )

        if response.status_code != 200:
            print(f"Erro HTTP {response.status_code} na busca ML")
            return []

        html_lower = response.text.lower()

        if "captcha" in html_lower or "digite os caracteres" in html_lower:
            print("Mercado Livre retornou captcha/bloqueio.")
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        resultados = []

        links = soup.select("a.poly-component__title")

        if not links:
            links = soup.select("a.ui-search-link")

        if not links:
            links = soup.select("a[href*='/MLB-']")

        for link_el in links:
            if len(resultados) >= limite:
                break

            try:
                nome = link_el.get_text(" ").strip()
                link = link_el.get("href")

                if not nome or not link:
                    continue

                card = link_el

                for _ in range(6):
                    if card.parent:
                        card = card.parent

                    preco_el = (
                        card.select_one(".andes-money-amount__fraction")
                        or card.select_one(".price-tag-fraction")
                        or card.select_one(".poly-price__current .andes-money-amount__fraction")
                    )

                    if preco_el:
                        break

                if not preco_el:
                    continue

                preco = limpar_preco(preco_el.get_text(" "))

                if not preco:
                    continue

                resultados.append({
                    "nome": nome,
                    "url": link,
                    "preco": preco,
                    "site": "Mercado Livre"
                })

            except Exception:
                continue

        return resultados

    except Exception as erro:
        print(f"Erro ao buscar produtos no Mercado Livre: {erro}")
        return []