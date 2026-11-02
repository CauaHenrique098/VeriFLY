MAX_ATTEMPTS = 2
STOP = MAX_ATTEMPTS - 1

def search_latam_airlines(context, reserve):

    for attempts in range(1, MAX_ATTEMPTS, 1):
    
        try:
            context.clear_cookies()

            page = context.new_page()

            page.goto(
                reserve, 
                wait_until="domcontentloaded"
            )


            if page.wait_for_selector('//*[@id="cookies-politics-button"]', timeout=100000).is_visible():     

                accept_cookies = page.locator('//*[@id="cookies-politics-button"]')

                if accept_cookies.is_visible():
                    accept_cookies.click()

                flights_info_in_company = page.locator('//*[@id="__next"]/section/section/section/main/section[2]/section[1]/section[1]/section[1]')

                quantity_flights = flights_info_in_company.locator(":scope > #AccordionGroupWrapper").count()

                if quantity_flights > 1:

                    flights_in_company = {
                        "locator": None,

                        "outbound_flight_infos": {
                            "origin": {
                                "airport": page.locator('#order-detail-city-origin-outbound').text_content(),
                                "date": page.locator('//*[@id="order-detail-trip-date-outbound"]').text_content(),
                                "hour": page.locator('//*[@id="order-detail-departure-time-outbound"]/span').text_content()
                            },

                            "destiny": {
                                "airport": page.locator('#order-detail-city-destination-outbound').text_content(),
                                "date": page.locator('//*[@id="order-detail-trip-date-outbound"]').text_content(),
                                "hour": page.locator('//*[@id="order-detail-arrival-time-outbound"]/span').text_content()
                            }
                        },

                        "return_flight_infos": {
                            "origin": {
                                "airport": page.locator('#order-detail-city-origin-inbound').text_content(),
                                "date": page.locator('//*[@id="order-detail-trip-date-inbound"]').text_content(),
                                "hour": page.locator('//*[@id="order-detail-departure-time-inbound"]/span').text_content()
                            },

                            "destiny": {
                                "airport": page.locator('#order-detail-city-destination-inbound').text_content(),
                                "date": page.locator('//*[@id="order-detail-trip-date-inbound"]').text_content(),
                                "hour": page.locator('//*[@id="order-detail-arrival-time-inbound"]/span').text_content()
                            }
                        }
                    }

                else: 

                    flights_in_company = {
                        "locator": None,

                        "outbound_flight_infos": {
                            "origin": {
                                "airport": page.locator('order-detail-iata-origin-outbound').nth(0).text_content(),
                                "date": page.locator('//*[@id="order-detail-trip-date-outbound"]').text_content(),
                                "hour": page.locator('//*[@id="order-detail-departure-time-outbound"]/span').text_content()
                            },

                            "destiny": {
                                "airport": page.locator('order-detail-iata-origin-outbound').nth(1).text_content(),
                                "date": page.locator('//*[@id="order-detail-trip-date-outbound"]').text_content(),
                                "hour": page.locator('//*[@id="order-detail-arrival-time-outbound"]/span').text_content()
                            }
                        }
                    }

                print(f"finalizado!!")

            else:

                page.close()

                print("VERIFICAR RESERVA DA GOL")

                page.close()

                continue
            
            page.close()

            return flights_in_company
            
        except Exception as error:  

            print(f"\n\n{error}\nAcessando novamente...")

            if attempts == STOP: #Verifica se já ocorreram 5 tentativas

                flights_in_company = {
                    "locator": None,

                    "outbound_flight_infos": {
                        "origin": {
                            "airport": None,
                            "date": None,
                            "hour": None
                        },

                        "destiny": {
                            "airport": None,
                            "date": None,
                            "hour": None
                        }
                    },

                    "return_flight_infos": {
                        "origin": {
                            "airport": None,
                            "date": None,
                            "hour": None
                        },

                        "destiny": {
                            "airport": None,
                            "date": None,
                            "hour": None
                        }
                    }
                }
              
                page.close()
                
                return flights_in_company

            page.close()

            continue
