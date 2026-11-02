from playwright.sync_api import sync_playwright

from block_resources import block_resources
from azul import search_azul_viagens
from gol import search_gol_airlines

import json

reserve_to_verifier = [] #URL do banco de dados para conferir
verified_flights = []

def main(reserve):

    with sync_playwright() as pw:

        browser = pw.chromium.launch(headless=False)

        context = browser.new_context(reduced_motion="reduce")

        context.route("**/*", block_resources)

        
        verified_flights.append(search_gol_airlines(context, reserve))
        
        browser.close()

        print("\n finalizado!!")


if __name__ == "__main__":
    main(reserve_to_verifier)