from flask import Flask, render_template, request, jsonify
from firebase_db import db

app = Flask(__name__)


# ---------- Páginas ----------
# Usei os nomes com .html para os links do menu continuarem funcionando

@app.route("/")
def login():
    return render_template("login.html")

@app.route("/dashboard.html")
def dashboard():
    return render_template("dashboard.html")

@app.route("/history.html")
def history():
    return render_template("history.html")

@app.route("/new_reserve.html")
def new_reserve():
    return render_template("new_reserve.html")


# ---------- API: salvar reserva no Firestore ----------

@app.route("/api/reservas", methods=["POST"])
def create_reserve():
    data = request.get_json()

    # Suporta as chaves enviadas pelo new_reserve.js (name, codeReserve, stretches)
    nome = data.get("name") or data.get("nome") if data else None
    codigo_reserva = data.get("codeReserve") or data.get("codigoReserva") if data else None
    trechos = data.get("stretches") or data.get("trechos") if data else None

    if not data or not nome or not codigo_reserva:
        return jsonify({"erro": "Dados incompletos"}), 400

    if not trechos:
        return jsonify({"erro": "Informe ao menos um trecho"}), 400

    db.collection("reservas").document(codigo_reserva).set(data)
    return jsonify({"status": "ok", "id": codigo_reserva}), 201

# ---------- API: Comparador e Dados do Dashboard ----------

@app.route("/api/dashboard", methods=["GET"])
def get_dashboard_data():
    """
    Executa o fluxo do comparador sobre as reservas do banco e retorna
    os contadores atualizados e a lista de voos classificados.
    Para usar o Playwright real em vez do mock, passe ?mock=false na URL.
    """
    use_mock = request.args.get("mock", "true").lower() != "false"
    result = run_comparator_for_all_reserves(use_mock=use_mock)
    return jsonify(result), 200


# ---------- API: Ações Manuais (Botões RESOLVIDO e REALIZADO) ----------

@app.route("/api/reservas/<codigo_reserva>/status", methods=["PATCH"])
def update_flight_status(codigo_reserva):
    """
    Atualiza manualmente o status de um trecho para 'solved' (Resolvido)
    ou 'completed' (Realizado) no Firestore.
    """
    body = request.get_json()
    new_status = body.get("status")
    stretch_order = int(body.get("order", 1))

    if new_status not in ("solved", "completed"):
        return jsonify({"erro": "Status inválido. Use 'solved' ou 'completed'."}), 400

    doc_ref = db.collection("reservas").document(codigo_reserva)
    doc = doc_ref.get()

    if not doc.exists:
        return jsonify({"erro": "Reserva não encontrada"}), 404

    reserve_data = doc.to_dict()
    stretches = reserve_data.get("stretches") or reserve_data.get("trechos") or []

    updated = False
    for idx, stretch in enumerate(stretches):
        order = int(stretch.get("order", idx + 1))
        if order == stretch_order:
            # Regra: Botão RESOLVIDO só é aplicável a voos com alteração (Alta ou Baixa prioridade)
            if new_status == "solved" and stretch.get("status") not in ("high_priority", "low_priority"):
                return jsonify({"erro": "Apenas voos alterados podem ser marcados como Resolvidos."}), 400

            stretch["status"] = new_status
            updated = True
            break

    if not updated:
        return jsonify({"erro": "Trecho não encontrado"}), 404

    doc_ref.update({"stretches": stretches})
    return jsonify({"status": "ok", "codeReserve": codigo_reserva, "newStatus": new_status}), 200


if __name__ == "__main__":
    app.run(debug=True)