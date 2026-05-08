import re
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"
}


def limpar_preco(texto):
    if not texto:
        return None

    texto = texto.replace("\xa0", " ").replace("R$", "").strip()
    match = re.search(r"[\d\.]+,\d{2}|[\d\.]+", texto)

    if not match:
        return None

    valor = match.group().replace(".", "").replace(",", ".")

    try:
        return float(valor)
    except ValueError:
        return None


def buscar_preco_generico(url):
    response = requests.get(url, headers=HEADERS, timeout=10)

    if response.status_code != 200:
        print(f"Erro HTTP {response.status_code} ao acessar {url}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    seletores = [
        ".a-price .a-offscreen",
        ".a-price-whole",
        ".andes-money-amount__fraction",
        ".price-tag-fraction",
        ".ui-pdp-price__second-line",
        ".ui-pdp-price__second-line .andes-money-amount__fraction",
        ".price"
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

    return None


def buscar_preco(url):
    return buscar_preco_generico(url)
