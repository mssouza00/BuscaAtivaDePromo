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
    seletores_preco_principal = [
        "span.a-price.apexPriceToPay",
        "span.a-price[data-a-color='priceToPay']",
        "#corePriceDisplay_desktop_feature_div span.a-price",
        "#corePrice_feature_div span.a-price",
        "#apex_desktop span.a-price",
        "#desktop_buybox span.a-price",
    ]

    for seletor in seletores_preco_principal:
        elementos = soup.select(seletor)

        for elemento in elementos:
            whole = elemento.select_one(".a-price-whole")
            fraction = elemento.select_one(".a-price-fraction")

            if whole:
                texto = whole.get_text(strip=True)

                if fraction:
                    texto += "," + fraction.get_text(strip=True)

                preco = limpar_preco(texto)

                if preco and preco > 100:
                    return {
                        "preco": preco,
                        "origem": f"Amazon: preço principal {seletor}"
                    }

    seletores_offscreen = [
        "span.a-price.apexPriceToPay span.a-offscreen",
        "span.a-price[data-a-color='priceToPay'] span.a-offscreen",
        "#corePriceDisplay_desktop_feature_div span.a-offscreen",
        "#corePrice_feature_div span.a-offscreen",
        "#apex_desktop span.a-offscreen",
        "#desktop_buybox span.a-offscreen",
    ]

    for seletor in seletores_offscreen:
        elementos = soup.select(seletor)

        for elemento in elementos:
            texto = elemento.get_text(" ", strip=True)
            preco = limpar_preco(texto)

            if preco and preco > 100:
                return {
                    "preco": preco,
                    "origem": f"Amazon: offscreen {seletor}"
                }

    texto = soup.get_text(" ")
    valores = re.findall(r"R\$\s?[\d\.]+,\d{2}", texto)

    candidatos = []

    for valor in valores:
        preco = limpar_preco(valor)

        if preco and preco > 500:
            candidatos.append(preco)

    if candidatos:
        return {
            "preco": min(candidatos),
            "origem": "Amazon: menor preço encontrado no texto"
        }

    return None


def buscar_preco_mercado_livre(soup):
    blocos = [
        ".ui-pdp-price__second-line",
        ".ui-pdp-price",
        ".ui-pdp-container__row--price",
    ]

    for seletor in blocos:
        bloco = soup.select_one(seletor)

        if not bloco:
            continue

        fraction = bloco.select_one(".andes-money-amount__fraction")
        cents = bloco.select_one(".andes-money-amount__cents")

        if fraction:
            texto = fraction.get_text(strip=True)

            if cents:
                texto += "," + cents.get_text(strip=True)

            preco = limpar_preco(texto)

            if preco:
                return {
                    "preco": preco,
                    "origem": f"Mercado Livre: {seletor}"
                }

    texto = soup.get_text(" ")
    valores = re.findall(r"R\$\s?[\d\.]+,\d{2}|R\$\s?[\d\.]+", texto)

    candidatos = []

    for valor in valores:
        preco = limpar_preco(valor)

        if preco and preco > 10:
            candidatos.append(preco)

    if candidatos:
        return {
            "preco": candidatos[0],
            "origem": "Mercado Livre: texto da página"
        }

    return None


def buscar_preco_meta(soup):
    metas = [
        {"property": "product:price:amount"},
        {"property": "og:price:amount"},
        {"itemprop": "price"},
    ]

    for meta in metas:
        elemento = soup.find("meta", meta)

        if elemento:
            preco = limpar_preco(elemento.get("content"))

            if preco:
                return {
                    "preco": preco,
                    "origem": f"Meta: {meta}"
                }

    return None


def buscar_preco_json(soup):
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        try:
            if not script.string:
                continue

            dados = json.loads(script.string)
            itens = dados if isinstance(dados, list) else [dados]

            for item in itens:
                if not isinstance(item, dict):
                    continue

                offers = item.get("offers")

                if isinstance(offers, dict):
                    price = offers.get("price")

                    if price:
                        return {
                            "preco": float(str(price).replace(",", ".")),
                            "origem": "JSON-LD: offers.price"
                        }

                if isinstance(offers, list):
                    for offer in offers:
                        price = offer.get("price")

                        if price:
                            return {
                                "preco": float(str(price).replace(",", ".")),
                                "origem": "JSON-LD: offers[].price"
                            }

        except Exception:
            continue

    return None


def buscar_preco_generico(soup):
    texto = soup.get_text(" ")
    valores = re.findall(r"R\$\s?[\d\.]+,\d{2}", texto)

    candidatos = []

    for valor in valores:
        preco = limpar_preco(valor)

        if preco and preco > 10:
            candidatos.append(preco)

    if candidatos:
        return {
            "preco": candidatos[0],
            "origem": "Genérico: texto da página"
        }

    return None


def buscar_preco_detalhado(url):
    url = limpar_url(url)

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=10
        )

        if response.status_code != 200:
            print(f"Erro HTTP {response.status_code} ao acessar {url}")
            return None

        html_lower = response.text.lower()

        if "captcha" in html_lower or "digite os caracteres" in html_lower:
            print("Site retornou captcha/bloqueio.")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        if "amazon.com" in url:
            resultado = buscar_preco_amazon(soup)
            if resultado:
                return resultado

        if "mercadolivre.com" in url:
            resultado = buscar_preco_mercado_livre(soup)
            if resultado:
                return resultado

        resultado = buscar_preco_meta(soup)
        if resultado:
            return resultado

        resultado = buscar_preco_json(soup)
        if resultado:
            return resultado

        resultado = buscar_preco_generico(soup)
        if resultado:
            return resultado

        print("Preço não encontrado.")
        return None

    except Exception as erro:
        print(f"Erro no scraper: {erro}")
        return None


def buscar_preco(url):
    resultado = buscar_preco_detalhado(url)

    if resultado:
        return resultado["preco"]

    return None