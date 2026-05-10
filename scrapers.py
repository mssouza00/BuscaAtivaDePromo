import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")

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


# ─── Utilitários ──────────────────────────────────────────────────────────────

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
    texto = texto.replace("\xa0", " ").replace("R$", "").strip()
    match = re.search(r"[\d\.]+,\d{2}|[\d\.]+", texto)
    if not match:
        return None
    valor = match.group().replace(".", "").replace(",", ".")
    try:
        return float(valor)
    except Exception:
        return None


def fazer_requisicao(url, usar_scraperapi=False):
    """
    Faz a requisição HTTP.
    Se usar_scraperapi=True, roteia pelo ScraperAPI para evitar bloqueios.
    """
    if usar_scraperapi:
        if not SCRAPERAPI_KEY:
            logging.error("SCRAPERAPI_KEY não configurada no .env")
            return None

        scraperapi_url = (
            f"http://api.scraperapi.com"
            f"?api_key={SCRAPERAPI_KEY}"
            f"&url={requests.utils.quote(url, safe='')}"
            f"&country_code=br"
        )

        try:
            response = requests.get(scraperapi_url, timeout=30)
            logging.info(f"ScraperAPI status: {response.status_code} para {url}")
            return response
        except Exception as e:
            logging.error(f"Erro ScraperAPI: {e}")
            return None

    else:
        try:
            response = requests.Session().get(url, headers=HEADERS, timeout=10)
            return response
        except Exception as e:
            logging.error(f"Erro requisição direta: {e}")
            return None


# ─── Amazon ───────────────────────────────────────────────────────────────────

def buscar_preco_amazon(soup):
    """
    Busca o preço à vista nos seletores do bloco principal de compra.
    """
    seletores_prioritarios = [
        "#corePriceDisplay_desktop_feature_div span.a-price.apexPriceToPay",
        "#corePriceDisplay_desktop_feature_div span.a-price.priceToPay",
        "#corePrice_feature_div span.a-price.apexPriceToPay",
        "#corePrice_feature_div span.a-price.priceToPay",
        "span.a-price.apexPriceToPay",
        "span.a-price.priceToPay",
        "#desktop_buybox span.a-price",
        "#buybox span.a-price",
    ]

    for seletor in seletores_prioritarios:
        elemento = soup.select_one(seletor)
        if not elemento:
            continue

        offscreen = elemento.select_one(".a-offscreen")
        if offscreen:
            preco = limpar_preco(offscreen.get_text(" ", strip=True))
            if preco and preco > 1:
                logging.info(f"Amazon preço via '{seletor}': R$ {preco}")
                return {"preco": preco, "origem": f"Amazon via ScraperAPI ({seletor})"}

        whole    = elemento.select_one(".a-price-whole")
        fraction = elemento.select_one(".a-price-fraction")
        if whole:
            texto = whole.get_text("", strip=True).rstrip(",").rstrip(".")
            if fraction:
                texto += "," + fraction.get_text("", strip=True)
            preco = limpar_preco(texto)
            if preco and preco > 1:
                logging.info(f"Amazon preço (whole/fraction) via '{seletor}': R$ {preco}")
                return {"preco": preco, "origem": f"Amazon via ScraperAPI ({seletor})"}

    logging.warning("Amazon: nenhum seletor de preço funcionou.")
    return None


# ─── Mercado Livre ────────────────────────────────────────────────────────────

def buscar_preco_mercado_livre(soup):
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
        cents    = bloco.select_one(".andes-money-amount__cents")

        if fraction:
            texto = fraction.get_text("", strip=True)
            if cents:
                texto += "," + cents.get_text("", strip=True)
            preco = limpar_preco(texto)
            if preco and preco > 1:
                logging.info(f"Mercado Livre via '{seletor}': R$ {preco}")
                return {"preco": preco, "origem": f"Mercado Livre ({seletor})"}

    # Fallback por texto
    texto  = soup.get_text(" ")
    valores = re.findall(r"R\$\s?[\d\.]+,\d{2}", texto)
    for valor in valores:
        preco = limpar_preco(valor)
        if preco and preco > 1:
            logging.warning(f"Mercado Livre fallback texto: R$ {preco}")
            return {
                "preco": preco,
                "origem": "Mercado Livre (fallback texto) — verifique se é o preço correto"
            }

    return None


# ─── Entrada principal ────────────────────────────────────────────────────────

def buscar_preco_detalhado(url):
    url = limpar_url(url)
    logging.info(f"Consultando: {url}")

    # Amazon → usa ScraperAPI para evitar bloqueio
    if "amazon.com" in url:
        response = fazer_requisicao(url, usar_scraperapi=True)

        if not response or response.status_code != 200:
            status = response.status_code if response else "sem resposta"
            return {"preco": None, "origem": f"Erro ao acessar Amazon via ScraperAPI (status {status})"}

        html_lower = response.text.lower()
        if "captcha" in html_lower or "digite os caracteres" in html_lower:
            return {"preco": None, "origem": "ScraperAPI: CAPTCHA ainda presente — tente novamente"}

        soup = BeautifulSoup(response.text, "html.parser")
        resultado = buscar_preco_amazon(soup)
        return resultado or {
            "preco": None,
            "origem": "Amazon: preço não encontrado no HTML. O produto pode estar indisponível."
        }

    # Mercado Livre → acesso direto (sem bloqueio)
    if "mercadolivre.com" in url:
        response = fazer_requisicao(url, usar_scraperapi=False)

        if not response or response.status_code != 200:
            status = response.status_code if response else "sem resposta"
            return {"preco": None, "origem": f"Erro HTTP {status} no Mercado Livre"}

        soup = BeautifulSoup(response.text, "html.parser")
        resultado = buscar_preco_mercado_livre(soup)
        return resultado or {"preco": None, "origem": "Preço não encontrado no HTML do Mercado Livre"}

    return {"preco": None, "origem": "URL não reconhecida (use links da Amazon ou Mercado Livre)"}


def buscar_preco(url):
    resultado = buscar_preco_detalhado(url)
    if resultado and resultado.get("preco"):
        return resultado["preco"]
    return None