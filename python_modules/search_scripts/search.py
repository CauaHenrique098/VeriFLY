from playwright.sync_api import sync_playwright

from block_resources import block_resources
from azul import search_azul_viagens
from gol import search_gol_airlines
from latam import search_latam_airlines

import json

reserves = [
    "https://www.latamairlines.com/br/pt/minhas-viagens/second-detail?orderId=LA9576472NKRJ&lastname=FILHO",
    "https://www.latamairlines.com/br/pt/minhas-viagens/second-detail?orderId=LA9576575UBCY&lastname=TINOCO",
    "https://www.latamairlines.com/br/pt/minhas-viagens/second-detail?orderId=LA9579510EECH&lastname=COSTA",
    "https://www.latamairlines.com/br/pt/minhas-viagens/second-detail?orderId=LA9579949EUUU&lastname=ABEKAWA"
]

verified_flights = []

def search_flights_in_company(reserve):

    with sync_playwright() as pw:

        browser = pw.chromium.launch(headless=False)

        context = browser.new_context(reduced_motion="reduce")

        context.route("**/*", block_resources)

        verified_flights.append(search_latam_airlines(context, reserve))
        
        browser.close()


if __name__ == "__main__":
    for reserve in reserves:
        search_flights_in_company(reserve)

    with open("python_modules/arquivo.json", 'w') as flights:
        json.dump(verified_flights, flights, indent=4, ensure_ascii=False)