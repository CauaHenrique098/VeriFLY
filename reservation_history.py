"""Eventos permanentes gravados na mesma transação da alteração da reserva."""

from copy import deepcopy
from datetime import datetime, timezone

from google.cloud import firestore


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def history_snapshot(reserve):
    if reserve is None:
        return None
    fields = ("name", "codeReserve", "folder", "telefone", "status", "segmentResults", "lastCheckError")
    snapshot = {key: deepcopy(reserve.get(key)) for key in fields}
    segment_fields = ("order", "origin", "destination", "type", "company", "departureOriginal", "arrivalOriginal")
    snapshot["stretches"] = [
        {key: segment.get(key) for key in segment_fields}
        for segment in reserve.get("stretches") or []
    ]
    return snapshot


def append_event(writer, reserve_ref, kind, before, after):
    timestamp = utc_now()
    event_ref = reserve_ref.collection("historico").document()
    writer.set(event_ref, {
        "type": kind, "occurredAt": timestamp,
        "before": history_snapshot(before), "after": history_snapshot(after),
    })
    metadata = {"historyLastAt": timestamp, "historyLastType": kind}
    writer.update(reserve_ref, metadata)
    after.update(metadata)


def save_reserve(db, data):
    ref = db.collection("reservas").document(data["codeReserve"])

    @firestore.transactional
    def save(transaction):
        snapshot = ref.get(transaction=transaction)
        before = snapshot.to_dict() if snapshot.exists else None
        # Campos internos não podem ser definidos pelo formulário.
        reserve = {key: deepcopy(data.get(key)) for key in ("name", "codeReserve", "telefone", "folder", "stretches")}
        reserve.update({"status": "pending", "createdAt": (before or {}).get("createdAt") or utc_now()})
        transaction.set(ref, reserve)
        append_event(transaction, ref, "updated" if before else "created", before, reserve)
        return reserve

    return save(db.transaction())


def get_history(db, reserve_id, limit=25, cursor=None):
    ref = db.collection("reservas").document(reserve_id)
    snapshot = ref.get()
    if not snapshot.exists:
        raise LookupError(reserve_id)
    events = ref.collection("historico")
    query = events.order_by("occurredAt", direction=firestore.Query.DESCENDING)
    if cursor:
        if "/" in cursor:
            raise ValueError("Página de histórico inválida")
        cursor_snapshot = events.document(cursor).get()
        if not cursor_snapshot.exists:
            raise ValueError("Página de histórico inválida")
        query = query.start_after(cursor_snapshot)
    snapshots = list(query.limit(limit + 1).stream())
    page = snapshots[:limit]
    return {
        "reserve": {**snapshot.to_dict(), "id": reserve_id},
        "events": [{**event.to_dict(), "id": event.id} for event in page],
        "nextCursor": page[-1].id if len(snapshots) > limit else None,
    }
