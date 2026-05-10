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


def buscar_preco_mercado_livre(soup):
    blocos_preco = [
        ".ui-pdp-price__second-line",
        ".ui-pdp-price",
        ".ui-pdp-container__row--price",
    ]

    for bloco_selector in blocos_preco:
        bloco = soup.select_one(bloco_selector)

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
                    "origem": f"Mercado Livre: {bloco_selector}"
                }

    seletores = [
        ".andes-money-amount__fraction",
        ".price-tag-fraction",
        ".poly-price__current .andes-money-amount__fraction",
    ]

    for seletor in seletores:
        elemento = soup.select_one(seletor)

        if elemento:
            preco = limpar_preco(elemento.get_text(" "))

            if preco:
                return {
                    "preco": preco,
                    "origem": f"Mercado Livre: {seletor}"
                }

    texto = soup.get_text(" ")

    match = re.search(r"R\$\s?[\d\.]+,\d{2}", texto)
    if match:
        return {
            "preco": limpar_preco(match.group()),
            "origem": "Mercado Livre: texto da página com centavos"
        }

    match = re.search(r"R\$\s?[\d\.]+", texto)
    if match:
        return {
            "preco": limpar_preco(match.group()),
            "origem": "Mercado Livre: texto da página"
        }

    return None


def buscar_preco_amazon(soup):
    seletores_prioritarios = [
        "#corePrice_feature_div .a-price .a-offscreen",
        "#corePrice_feature_div span.a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-offscreen",
        ".apexPriceToPay .a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "#priceblock_saleprice",
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

    textos_invalidos = [
        "de:",
        "preço anterior",
        "economize",
        "cupom",
        "parcelas",
        "sem juros"
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


def buscar_preco_meta(soup):
    metas = [
        {"property": "product:price:amount"},
        {"property": "og:price:amount"},
        {"itemprop": "price"},
    ]

    for meta in metas:
        elemento = soup.find("meta", meta)

        if elemento:
            conteudo = elemento.get("content")
            preco = limpar_preco(conteudo)

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

    match = re.search(r"R\$\s?[\d\.]+,\d{2}", texto)

    if match:
        return {
            "preco": limpar_preco(match.group()),
            "origem": "Genérico: texto da página"
        }

    return None


def buscar_preco_detalhado(url):
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

        if "mercadolivre.com" in url:
            resultado = buscar_preco_mercado_livre(soup)
            if resultado:
                return resultado

        if "amazon.com" in url:
            resultado = buscar_preco_amazon(soup)
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