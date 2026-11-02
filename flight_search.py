"""
Adaptador do BUSCADOR de voos.

O comparador (comparator.py) chama apenas a função search_flight(url, company, reserve).
O que ela devolve tem SEMPRE o mesmo formato do scraper da Azul (search_azul_viagens):

{
    "locator": "AGG12V",
    "outbound_flight_infos": {
        "origin":  {"airport": "UDI", "date": "23/05/2027", "hour": "12:55"},
        "destiny": {"airport": "MCZ", "date": "23/05/2027", "hour": "15:30"}
    },
    "return_flight_infos": {...}   # só existe em reservas de ida e volta
}

Dois modos (variável de ambiente VERIFLY_USE_MOCK):
  VERIFLY_USE_MOCK=1 (padrão) -> MOCK: não acessa a internet, inventa uma resposta.
  VERIFLY_USE_MOCK=0          -> scraper real da Azul (Playwright).
"""

import os
import sys
import hashlib
from datetime import datetime, timedelta

USE_MOCK = os.environ.get("VERIFLY_USE_MOCK", "1") == "1"

# Só vale para o MOCK: auto | same | hour | date
#   same -> voo igual ao cadastrado (vira "Voos confirmados")
#   hour -> horário atrasado em 55 min (vira alta ou baixa prioridade)
#   date -> data adiantada em 1 dia (vira alta ou baixa prioridade)
#   auto -> escolhe um dos três com base no código da reserva (varia entre reservas)
MOCK_SCENARIO = os.environ.get("VERIFLY_MOCK_SCENARIO", "auto")


def search_flight(url, company, reserve=None):
    """Recebe a URL da reserva (passo 2 do fluxo) e devolve os dados da companhia."""

    if USE_MOCK:
        return _mock_search(url, reserve)

    if company == "azul":
        return _search_azul(url)

    raise NotImplementedError(f"O buscador da companhia '{company}' ainda não foi implementado")


# ---------------------------------------------------------------------------
# BUSCADOR REAL (Azul)
# ---------------------------------------------------------------------------

def _search_azul(url):
    from playwright.sync_api import sync_playwright

    # AJUSTE AQUI se necessário: pasta onde ficam block_resources.py e a pasta azul/
    sys.path.append(os.path.join(os.path.dirname(__file__), "python_modules"))

    from block_resources import block_resources
    from azul import search_azul_viagens

    with sync_playwright() as pw:
        # headless=True porque o Codespace não tem tela (o search.py usa False)
        browser = pw.chromium.launch(headless=True)

        try:
            context = browser.new_context(reduced_motion="reduce")
            context.route("**/*", block_resources)

            return search_azul_viagens(0, context, url)
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# MOCK (simula o retorno do scraper, no mesmo formato)
# ---------------------------------------------------------------------------

def _mock_search(url, reserve=None):
    reserve = reserve or {}
    stretches = reserve.get("stretches") or []
    code = reserve.get("codeReserve", "MOCK00")

    scenario = MOCK_SCENARIO
    if scenario == "auto":
        scenario = ["same", "hour", "date"][int(hashlib.md5(code.encode()).hexdigest(), 16) % 3]

    result = {"locator": code}

    # O scraper só devolve ida (outbound) e volta (return)
    for key, segment in zip(("outbound_flight_infos", "return_flight_infos"), stretches[:2]):
        departure = _parse_saved(segment.get("departureOriginal"))
        arrival = _parse_saved(segment.get("arrivalOriginal")) or departure

        if departure is None:
            continue

        # Só o primeiro trecho sofre a alteração simulada
        if key == "outbound_flight_infos":
            if scenario == "hour":
                departure += timedelta(minutes=55)
            elif scenario == "date":
                departure -= timedelta(days=1)

        result[key] = {
            "origin": {
                "airport": segment.get("origin"),
                "date": departure.strftime("%d/%m/%Y"),
                "hour": departure.strftime("%H:%M")
            },
            "destiny": {
                "airport": segment.get("destination"),
                "date": arrival.strftime("%d/%m/%Y"),
                "hour": arrival.strftime("%H:%M")
            }
        }

    return result


def _parse_saved(value):
    """'2026-10-07T13:30' ou '2026-10-07' -> datetime (sem hora vira 12:00)."""
    if not value:
        return None

    for pattern in ("%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, pattern)
            return parsed.replace(hour=12) if pattern == "%Y-%m-%d" else parsed
        except ValueError:
            continue

    return None
