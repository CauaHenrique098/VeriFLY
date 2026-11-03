from flask import Flask, render_template, request, jsonify

from firebase_db import db
from comparator import set_manual_status
from verification_queue import attach_jobs, request_check
from reservation_history import get_history, save_reserve


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


# ---------- API: reservas no Firestore ----------

@app.route("/api/reservas", methods=["POST"])
def create_reserve():
    data = request.get_json()

    # Chaves iguais às enviadas pelo new_reserve.js
    if not data or not data.get("name") or not data.get("codeReserve"):
        return jsonify({"erro": "Dados incompletos"}), 400

    if not data.get("stretches"):
        return jsonify({"erro": "Informe ao menos um trecho"}), 400

    save_reserve(db, data)
    return jsonify({"status": "ok", "id": data["codeReserve"]}), 201


@app.route("/api/reservas", methods=["GET"])
def list_reserves():
    reserves = []

    for doc in db.collection("reservas").stream():
        reserve = doc.to_dict()
        reserve["id"] = doc.id
        reserves.append(reserve)

    return jsonify(attach_jobs(reserves))


@app.route("/api/reservas/<reserve_id>/historico", methods=["GET"])
def reserve_history(reserve_id):
    try:
        limit = int(request.args.get("limit", 25))
        if not 1 <= limit <= 100:
            raise ValueError("O limite deve estar entre 1 e 100")
        result = get_history(db, reserve_id, limit, request.args.get("cursor"))
    except LookupError:
        return jsonify({"erro": "Reserva não encontrada"}), 404
    except ValueError as error:
        return jsonify({"erro": str(error)}), 400
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------- API: comparador e ações manuais ----------

@app.route("/api/reservas/<reserve_id>/comparar", methods=["POST"])
def compare_reserve_route(reserve_id):
    try:
        reserve = request_check(reserve_id)
    except LookupError:
        return jsonify({"erro": "Reserva não encontrada"}), 404

    return jsonify(reserve), 202


@app.route("/api/reservas/<reserve_id>/status", methods=["PATCH"])
def update_reserve_status(reserve_id):
    data = request.get_json() or {}

    try:
        reserve = set_manual_status(reserve_id, data.get("status"))
    except LookupError:
        return jsonify({"erro": "Reserva não encontrada"}), 404
    except ValueError as error:
        return jsonify({"erro": str(error)}), 400

    return jsonify(reserve)


if __name__ == "__main__":
    app.run(debug=True)
