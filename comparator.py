from datetime import datetime
from firebase_db import db

# Tentativa de importar o buscador real da Azul já existente no projeto
try:
    from playwright.sync_api import sync_playwright
    from block_resources import block_resources
    from azul.search_flights import search_azul_viagens
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ---------- PASSO 2: Função de Busca (Integração Real + Mock) ----------

def fetch_flight_from_airline(reserve_url, company="azul", pnr="MOCK123", use_mock=True):
    """
    Recebe a variável reserve_url vinda do banco de dados e retorna os dados atuais do voo.
    Mantém o exato formato de retorno de search_flights.py e arquivo.json.
    """
    if not reserve_url:
        return None

    # Execução real via Playwright (quando use_mock=False e a cia for Azul)
    if not use_mock and PLAYWRIGHT_AVAILABLE and company.lower() == "azul":
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(reduced_motion="reduce")
            context.route("**/*", block_resources)
            flight_data = search_azul_viagens(0, context, reserve_url)
            browser.close()
            return flight_data

    # Mock claro do retorno do buscador (seguindo a estrutura de arquivo.json)
    # Dica para testes: se a URL terminar com "?alterado=1", simula mudança de horário
    if "alterado=1" in reserve_url:
        return {
            "locator": pnr,
            "outbound_flight_infos": {
                "origin": {
                    "airport": "CNF",
                    "date": "15/12/2026",
                    "hour": "16:45"  # Horário alterado para simulação
                },
                "destiny": {
                    "airport": "MCZ",
                    "date": "15/12/2026",
                    "hour": "19:00"
                }
            }
        }

    # Retorno padrão do Mock (extrai parâmetros ou retorna valores para teste)
    return {
        "locator": pnr,
        "outbound_flight_infos": {
            "origin": {
                "airport": "CNF",
                "date": "15/12/2026",
                "hour": "06:10"
            },
            "destiny": {
                "airport": "BPS",
                "date": "15/12/2026",
                "hour": "07:25"
            }
        }
    }


# ---------- Funções Auxiliares de Normalização de Data e Hora ----------

def parse_date(date_str):
    """
    Converte strings de data nos formatos 'YYYY-MM-DD' (salvo pelo input HTML)
    ou 'DD/MM/YYYY' (retornado pelo buscador) em um objeto datetime.date.
    """
    if not date_str:
        return None

    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def extract_original_date_and_hour(stretch):
    """
    Extrai data e horário originais do trecho salvo no banco.
    Suporta tanto campos separados (departureOriginal + departureHourOriginal)
    quanto datetime-local ('YYYY-MM-DDTHH:MM').
    """
    raw_departure = stretch.get("departureOriginal", "")
    raw_hour = stretch.get("departureHourOriginal", "")

    if "T" in raw_departure and not raw_hour:
        parts = raw_departure.split("T")
        return parts[0], parts[1][:5]

    return raw_departure, (raw_hour or "00:00").strip()


# ---------- PASSO 3: Comparação e Regras de Negócio (Classificação) ----------

def compare_and_classify_flight(stretch, scraped_data, flight_index=0):
    """
    Compara a data e horário de embarque salvos no banco com o retorno do buscador
    e classifica o voo segundo a regra dos 60 dias.
    """
    orig_date_str, orig_hour_str = extract_original_date_and_hour(stretch)
    orig_date = parse_date(orig_date_str)

    # Seleciona trecho de ida (outbound) ou volta (return) conforme a ordem
    flight_key = "outbound_flight_infos" if flight_index == 0 else "return_flight_infos"
    flight_info = (scraped_data or {}).get(flight_key) or (scraped_data or {}).get("outbound_flight_infos")

    if not flight_info or not flight_info.get("origin") or not flight_info["origin"].get("date"):
        # Caso o buscador não retorne dados válidos, mantém status anterior ou confirmado
        return {
            "status": stretch.get("status", "confirmed"),
            "hasChanged": False,
            "currentDate": orig_date.strftime("%d/%m/%Y") if orig_date else orig_date_str,
            "currentHour": orig_hour_str,
            "daysUntilFlight": None
        }

    scraped_origin = flight_info["origin"]
    scraped_date_str = scraped_origin.get("date", "").strip()
    scraped_hour_str = scraped_origin.get("hour", "").strip()
    scraped_date = parse_date(scraped_date_str)

    # Verifica se houve alteração na data OU no horário de embarque
    date_changed = (orig_date != scraped_date) if (orig_date and scraped_date) else (orig_date_str != scraped_date_str)
    hour_changed = (orig_hour_str != scraped_hour_str) if orig_hour_str else False
    has_changed = date_changed or hour_changed

    # Calcula a distância em dias até a data de embarque a partir da data atual
    reference_date = scraped_date or orig_date
    today = datetime.now().date()
    days_until_flight = (reference_date - today).days if reference_date else 999

    # Aplicação das Regras de Negócio:
    if not has_changed:
        status = "confirmed"          # Voos Confirmados: sem alteração
    else:
        if days_until_flight <= 60:
            status = "high_priority"  # Alta Prioridade: alterado E embarque em <= 60 dias
        else:
            status = "low_priority"   # Baixa Prioridade: alterado E embarque em > 60 dias

    return {
        "status": status,
        "hasChanged": has_changed,
        "originalDateFormatted": orig_date.strftime("%d/%m/%Y") if orig_date else orig_date_str,
        "originalHourFormatted": orig_hour_str,
        "currentDate": scraped_date.strftime("%d/%m/%Y") if scraped_date else scraped_date_str,
        "currentHour": scraped_hour_str,
        "daysUntilFlight": days_until_flight
    }


# ---------- PASSO 1: Fluxo Completo com o Banco de Dados (Firestore) ----------

def run_comparator_for_all_reserves(use_mock=True):
    """
    1. Busca todas as reservas no Firestore e armazena a URL da reserva em uma variável.
    2. Passa a variável reserve_url para a função de busca.
    3. Compara data/horário de embarque, atualiza o Firestore e retorna dados para o Dashboard.
    """
    reserves_ref = db.collection("reservas").stream()

    counters = {
        "high_priority": 0,
        "low_priority": 0,
        "confirmed": 0,
        "solved": 0,
        "completed": 0
    }
    flights_list = []

    for doc in reserves_ref:
        reserve_data = doc.to_dict()
        code_reserve = reserve_data.get("codeReserve") or reserve_data.get("codigoReserva") or doc.id
        client_name = reserve_data.get("name") or reserve_data.get("nome") or "Cliente"
        stretches = reserve_data.get("stretches") or reserve_data.get("trechos") or []
        updated_stretches = []

        for idx, stretch in enumerate(stretches):
            current_status = stretch.get("status")

            # Se o voo já foi marcado manualmente como RESOLVIDO ou REALIZADO pela equipe,
            # respeitamos a marcação manual no banco e somamos no respectivo contador.
            if current_status in ("solved", "completed"):
                orig_date_str, orig_hour_str = extract_original_date_and_hour(stretch)
                orig_date = parse_date(orig_date_str)
                stretch["originalDateFormatted"] = orig_date.strftime("%d/%m/%Y") if orig_date else orig_date_str
                stretch["originalHourFormatted"] = orig_hour_str
            else:
                # 1. Armazena o link (URL) da reserva do banco em uma variável
                reserve_url = stretch.get("urlReserve") or stretch.get("urlReserva") or ""
                company = stretch.get("company") or stretch.get("companhia") or "azul"

                # 2. Passa a variável como parâmetro para a função de busca
                scraped_flight = fetch_flight_from_airline(
                    reserve_url=reserve_url,
                    company=company,
                    pnr=code_reserve,
                    use_mock=use_mock
                )

                # 3. Compara os dados retornados com os dados originais do banco
                comparison = compare_and_classify_flight(stretch, scraped_flight, flight_index=idx)
                stretch.update(comparison)
                current_status = comparison["status"]

            # Atualiza contador correspondente
            if current_status in counters:
                counters[current_status] += 1

            updated_stretches.append(stretch)

            # Monta o item para exibição na listagem do Dashboard
            flights_list.append({
                "codeReserve": code_reserve,
                "clientName": client_name,
                "order": stretch.get("order", idx + 1),
                "company": (stretch.get("company") or "").upper(),
                "origin": stretch.get("origin", ""),
                "destination": stretch.get("destination", ""),
                "originalDate": stretch.get("originalDateFormatted", stretch.get("departureOriginal", "")),
                "originalHour": stretch.get("originalHourFormatted", stretch.get("departureHourOriginal", "")),
                "currentDate": stretch.get("currentDate", ""),
                "currentHour": stretch.get("currentHour", ""),
                "daysUntilFlight": stretch.get("daysUntilFlight"),
                "status": current_status
            })

        # Persiste os status atualizados no Firestore
        db.collection("reservas").document(code_reserve).update({
            "stretches": updated_stretches
        })

    return {
        "counters": counters,
        "flights": flights_list
    }