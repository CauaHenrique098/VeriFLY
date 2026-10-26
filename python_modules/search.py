from playwright.sync_api import sync_playwright

reserves_to_verifier = [
    'https://www.voeazul.com.br/br/pt/home/minhas-viagens/confirmacao?pnr=KWD7KQ&origin=UDI',
    'https://www.voeazul.com.br/br/pt/home/minhas-viagens?pnr=DT3MPB&origin=SLZ',
    'https://www.voeazul.com.br/br/pt/home/minhas-viagens/confirmacao?pnr=EPIFNK&origin=CNF'
]

all_verified_flights = []


for index in range(len(reserves_to_verifier)):
    with sync_playwright() as search_pass:
        browser = search_pass.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto(reserves_to_verifier[index])
        page.locator('//*[@id="onetrust-accept-btn-handler"]').click() #Aceitar cookies

        flights_info_in_company = page.locator("div.regular")
        quantity_flights = flights_info_in_company.locator(":scope > div").count()



        if quantity_flights > 1:
            create_reserve = {
                "flights": {
                    "locator": index,

                    "outbound_flight_infos": {
                        "origin": {
                            "airport": flights_info_in_company.locator("p").nth(0).text_content(),
                            "date": flights_info_in_company.locator("p").locator('time').nth(1).text_content(),
                            "hour": flights_info_in_company.locator("p").locator('time').nth(0).text_content()
                        },

                        "destiny": {
                            "airport": flights_info_in_company.locator("p").nth(4).text_content(),
                            "date": flights_info_in_company.locator("p").locator('time').nth(2).text_content(),
                            "hour": flights_info_in_company.locator("p").locator('time').nth(3).text_content()
                        }
                    },

                    "return_flight_infos": {
                        "origin": {
                            "airport": flights_info_in_company.locator("p").nth(4).text_content(),
                            "date": flights_info_in_company.locator("p").locator('time').nth(4).text_content(),
                            "hour": flights_info_in_company.locator("p").locator('time').nth(5).text_content()
                        },

                        "destiny": {
                            "airport": flights_info_in_company.locator("p").nth(11).text_content(),
                            "date": flights_info_in_company.locator("p").locator('time').nth(5).text_content(),
                            "hour": flights_info_in_company.locator("p").locator('time').nth(6).text_content()
                        }
                    }
                }
            }

        else:

            create_reserve = {
                "flights": {
                    "locator": index,

                    "outbound_flight_infos": {
                        "origin": {
                            "airport": flights_info_in_company.locator("p").nth(0).text_content(),
                            "date": flights_info_in_company.locator("p").locator('time').nth(1).text_content(),
                            "hour": flights_info_in_company.locator("p").locator('time').nth(0).text_content()
                        },

                        "destiny": {
                            "airport": flights_info_in_company.locator("p").nth(4).text_content(),
                            "date": flights_info_in_company.locator("p").locator('time').nth(2).text_content(),
                            "hour": flights_info_in_company.locator("p").locator('time').nth(3).text_content()
                        }
                    }
                }
            }

        all_verified_flights.append(create_reserve)