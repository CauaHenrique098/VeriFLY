from playwright.sync_api import sync_playwright

from block_resources import block_resources
from azul import search_azul_viagens
from gol import search_gol_airlines

import json




reserves = [
    "https://b2c.voegol.com.br/minhas-viagens/encontrar-viagem?codigoReserva=HDNVPO&origem=CNF&sobrenome=SILVA",
    "https://b2c.voegol.com.br/minhas-viagens/encontrar-viagem?codigoReserva=HZHYIH&origem=CNF&sobrenome=SILVA",
    "https://b2c.voegol.com.br/minhas-viagens/encontrar-viagem?codigoReserva=JQJNIP&origem=CNF&sobrenome=SILVA",
    "https://b2c.voegol.com.br/minhas-viagens/encontrar-viagem?codigoReserva=LCKYRH&origem=POA&sobrenome=CAIXETA",
    "https://b2c.voegol.com.br/minhas-viagens/encontrar-viagem?codigoReserva=YQDRYD&origem=BSB&sobrenome=SOUSA"
]




def main(reserves_to_verifier):

    all_verified_flights = []

    with sync_playwright() as pw:

        browser = pw.chromium.launch(headless=False)

        context = browser.new_context(reduced_motion="reduce")

        context.route("**/*", block_resources)

        for index, reserve in enumerate(reserves):
            all_verified_flights.append(search_gol_airlines(index, context, reserve))
        
        browser.close()

        with open("python_modules/arquivo.json", 'w') as flights:
            json.dump(all_verified_flights, flights, indent=4, ensure_ascii=False)

        print("\n finalizado!!")


if __name__ == "__main__":
    main(reserves)