"""
Adaptador dos BUSCADORES de voos (Playwright).

O comparador (comparator.py) chama apenas search_flight(url, company, reserve).
Esta função abre o navegador, executa o buscador da companhia escolhida e devolve
o dicionário que o próprio buscador retorna:

{
    "locator": "AGG12V",
    "outbound_flight_infos": {
        "origin":  {"airport": "UDI", "date": "23/05/2027", "hour": "12:55"},
        "destiny": {"airport": "MCZ", "date": "23/05/2027", "hour": "15:30"}
    },
    "return_flight_infos": {...}   # só existe em reservas de ida e volta
}

Companhias com buscador: azul e gol. (A LATAM ainda não tem buscador.)

Variável de ambiente opcional:
  VERIFLY_HEADLESS=0  -> abre o navegador visível (só funciona em máquina com tela;
                         no Codespace deixe o padrão, que é headless).
"""

import os
import sys
import inspect

from playwright.sync_api import sync_playwright

HEADLESS = os.environ.get("VERIFLY_HEADLESS", "1") != "0"

# Pastas onde podem estar block_resources.py e as pastas azul/ e gol/
# (relativas à pasta deste arquivo). A primeira que tiver a pasta "azul" é usada.
SCRAPER_FOLDERS = (
    ".",
    "python_modules",
    os.path.join("python_modules", "search_scripts"),
)


def _load_scrapers():
    """Importa os buscadores sem depender de qual pasta eles estão."""

    base = os.path.dirname(os.path.abspath(__file__))

    for folder in SCRAPER_FOLDERS:
        path = os.path.normpath(os.path.join(base, folder))

        if os.path.isdir(os.path.join(path, "azul")) and os.path.isdir(os.path.join(path, "gol")):
            if path not in sys.path:
                sys.path.insert(0, path)
            break
    else:
        raise ImportError(
            "Não encontrei as pastas 'azul' e 'gol' dos buscadores. "
            "Ajuste SCRAPER_FOLDERS em flight_search.py."
        )

    from block_resources import block_resources
    from azul import search_azul_viagens
    from gol import search_gol_airlines

    return block_resources, {
        "azul": search_azul_viagens,
        "gol": search_gol_airlines
    }


def _run_scraper(scraper, context, url):
    """Chama o buscador com a assinatura que ele tiver:
       azul -> (context, reserve)        gol -> (index_reserve, context, reserve)"""

    if "index_reserve" in inspect.signature(scraper).parameters:
        return scraper(0, context, url)

    return scraper(context, url)


def search_flight(url, company, reserve=None):
    """Recebe a URL da reserva (passo 2 do fluxo) e devolve os dados da companhia."""

    block_resources, scrapers = _load_scrapers()

    scraper = scrapers.get((company or "").lower())

    if scraper is None:
        raise NotImplementedError(f"A companhia '{company}' ainda não possui buscador")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)

        try:
            context = browser.new_context(reduced_motion="reduce")
            context.route("**/*", block_resources)

            return _run_scraper(scraper, context, url)
        finally:
            browser.close()
