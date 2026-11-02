"""
MÓDULO COMPARADOR DE VOOS

Fluxo (para uma reserva):
  1. Busca a reserva no Firestore e guarda a URL em uma variável (get_reserve_url)
  2. Passa a URL para o buscador (flight_search.search_flight)
  3. Compara data e horário de embarque do retorno da companhia com o que está salvo
  4. Classifica e grava o status no próprio documento da reserva
"""

import re
from datetime import date, datetime

from firebase_db import db
from flight_search import search_flight


COLLECTION = "reservas"

HIGH_PRIORITY_DAYS = 60  # <= 60 dias para o embarque = alta prioridade

# Status possíveis de uma reserva (campo "status" no Firestore)
STATUS_PENDING = "pending"            # cadastrada, ainda não verificada
STATUS_HIGH = "high_priority"         # alterada e embarque em até 60 dias
STATUS_LOW = "low_priority"           # alterada e embarque em mais de 60 dias
STATUS_CONFIRMED = "confirmed"        # sem alteração
STATUS_SOLVED = "solved"              # manual (botão RESOLVIDO)
STATUS_COMPLETED = "completed"        # manual (botão REALIZADO)

# O comparador só mexe nesses. "solved" e "completed" são definidos pela equipe
# e não podem ser sobrescritos por uma nova verificação.
COMPARABLE_STATUS = (STATUS_PENDING, STATUS_HIGH, STATUS_LOW, STATUS_CONFIRMED)


# ---------------------------------------------------------------------------
# Conversão de datas
# ---------------------------------------------------------------------------

def parse_saved_datetime(value):
    """Formato salvo pelo formulário: '2026-10-07T13:30' (ou só '2026-10-07').
    Devolve (date, 'HH:MM') ou (date, None) se não houver horário."""

    if not value:
        return None, None

    day_text, _, hour_text = value.partition("T")

    try:
        day = datetime.strptime(day_text, "%Y-%m-%d").date()
    except ValueError:
        return None, None

    return day, (hour_text[:5] or None)


def parse_company_datetime(date_text, hour_text):
    """Formato do scraper: date '23/05/2027' e hour '12:55'.
    Procura cada um pelo padrão, então funciona mesmo se vierem trocados
    (o scraper atual troca data e hora no 'destiny')."""

    joined = f"{date_text or ''} {hour_text or ''}"

    day_match = re.search(r"(\d{2})/(\d{2})/(\d{4})", joined)
    hour_match = re.search(r"(\d{1,2}):(\d{2})", joined)

    if not day_match:
        return None, None

    try:
        day = date(int(day_match.group(3)), int(day_match.group(2)), int(day_match.group(1)))
    except ValueError:
        return None, None

    hour = f"{int(hour_match.group(1)):02d}:{hour_match.group(2)}" if hour_match else None

    return day, hour


def to_iso(day, hour):
    return day.isoformat() + (f"T{hour}" if hour else "")


def clean_airport(text):
    match = re.search(r"\b[A-Z]{3}\b", (text or "").upper())
    return match.group(0) if match else (text or "").strip().upper()


# ---------------------------------------------------------------------------
# Passo 1: URL da reserva
# ---------------------------------------------------------------------------

def get_reserve_url(stretches):
    """Primeira URL preenchida entre os trechos (uma reserva = um link)."""
    return next((s.get("urlReserve") for s in stretches if s.get("urlReserve")), None)


# ---------------------------------------------------------------------------
# Passo 3: comparação
# ---------------------------------------------------------------------------

def extract_company_legs(company_data):
    """Transforma o retorno do scraper em uma lista de voos (ida e volta)."""

    legs = []

    for key in ("outbound_flight_infos", "return_flight_infos"):
        info = (company_data or {}).get(key)

        if not info:
            continue

        day, hour = parse_company_datetime(info["origin"].get("date"), info["origin"].get("hour"))

        if day is None:  # busca falhou (scraper devolve None em tudo)
            continue

        legs.append({
            "origin": clean_airport(info["origin"].get("airport")),
            "destination": clean_airport(info["destiny"].get("airport")),
            "departureDate": day,
            "departureHour": hour
        })

    return legs


def find_leg(segment, legs):
    """Acha o voo da companhia que corresponde ao trecho cadastrado (origem + destino)."""

    for leg in legs:
        if leg["origin"] == segment.get("origin") and leg["destination"] == segment.get("destination"):
            return leg

    return None


def compare_segment(segment, leg):
    """Compara data e horário de embarque de UM trecho."""

    saved_day, saved_hour = parse_saved_datetime(segment.get("departureOriginal"))

    result = {
        "order": segment.get("order"),
        "origin": segment.get("origin"),
        "destination": segment.get("destination"),
        "savedDeparture": segment.get("departureOriginal"),
        "newDeparture": None,
        "changedFields": [],
        "status": "not_found"  # not_found | same | changed
    }

    if leg is None or saved_day is None:
        return result

    if saved_day != leg["departureDate"]:
        result["changedFields"].append("date")

    # Se o cadastro não tem horário, só a data é comparada
    if saved_hour and leg["departureHour"] and saved_hour != leg["departureHour"]:
        result["changedFields"].append("hour")

    result["newDeparture"] = to_iso(leg["departureDate"], leg["departureHour"])
    result["status"] = "changed" if result["changedFields"] else "same"

    return result


# ---------------------------------------------------------------------------
# Regras de negócio: classificação
# ---------------------------------------------------------------------------

def classify(segment_results, today=None):
    changed = [r for r in segment_results if r["status"] == "changed"]

    if not changed:
        return STATUS_CONFIRMED

    today = today or date.today()

    # Embarque mais próximo entre os trechos alterados (data ORIGINAL cadastrada)
    nearest = min(parse_saved_datetime(r["savedDeparture"])[0] for r in changed)

    if (nearest - today).days <= HIGH_PRIORITY_DAYS:
        return STATUS_HIGH

    return STATUS_LOW


# ---------------------------------------------------------------------------
# Funções chamadas pelo app.py
# ---------------------------------------------------------------------------

def compare_reserve(reserve_id):
    """Executa o fluxo completo para uma reserva e devolve a reserva atualizada."""

    doc_ref = db.collection(COLLECTION).document(reserve_id)
    snapshot = doc_ref.get()

    if not snapshot.exists:
        raise LookupError(reserve_id)

    reserve = snapshot.to_dict()

    # Resolvido/Realizado são manuais: não são reclassificados
    if reserve.get("status", STATUS_PENDING) not in COMPARABLE_STATUS:
        return _with_id(reserve, reserve_id)

    stretches = reserve.get("stretches") or []
    reserve_url = get_reserve_url(stretches)                         # 1. URL em uma variável
    company = stretches[0].get("company") if stretches else None

    update = {"lastCheck": _now()}

    try:
        if not reserve_url:
            raise ValueError("Reserva sem URL cadastrada")

        company_data = search_flight(reserve_url, company, reserve)  # 2. URL vai para o buscador
        legs = extract_company_legs(company_data)

        if not legs:
            raise ValueError("A busca não retornou dados de voo")

        results = [compare_segment(s, find_leg(s, legs)) for s in stretches]  # 3. comparação

        has_changes = any(r["status"] == "changed" for r in results)
        has_missing = any(r["status"] == "not_found" for r in results)

        if has_missing and not has_changes:
            raise ValueError("Não foi possível localizar todos os trechos na companhia")

        update["status"] = classify(results)                         # 4. classificação
        update["segmentResults"] = results
        update["lastCheckError"] = None

    except Exception as error:
        # Falha na busca: mantém o status atual e registra o motivo
        print(f"[comparador] {reserve_id}: {error}")
        update["lastCheckError"] = str(error)

    doc_ref.update(update)
    reserve.update(update)

    return _with_id(reserve, reserve_id)


def set_manual_status(reserve_id, new_status):
    """Botões RESOLVIDO e REALIZADO. Devolve a reserva atualizada."""

    if new_status not in (STATUS_SOLVED, STATUS_COMPLETED):
        raise ValueError("Status inválido")

    doc_ref = db.collection(COLLECTION).document(reserve_id)
    snapshot = doc_ref.get()

    if not snapshot.exists:
        raise LookupError(reserve_id)

    reserve = snapshot.to_dict()
    current = reserve.get("status", STATUS_PENDING)

    if new_status == STATUS_SOLVED and current not in (STATUS_HIGH, STATUS_LOW):
        raise ValueError("Só é possível resolver voos que sofreram alteração")

    if new_status == STATUS_COMPLETED and current == STATUS_COMPLETED:
        raise ValueError("O voo já está como realizado")

    update = {
        "status": new_status,
        "previousStatus": current,
        "statusUpdatedAt": _now()
    }

    doc_ref.update(update)
    reserve.update(update)

    return _with_id(reserve, reserve_id)


def _with_id(reserve, reserve_id):
    reserve["id"] = reserve_id
    return reserve


def _now():
    return datetime.now().isoformat(timespec="seconds")
