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

    if not data or not data.get("nome") or not data.get("codigoReserva"):
        return jsonify({"erro": "Dados incompletos"}), 400

    if not data.get("trechos"):
        return jsonify({"erro": "Informe ao menos um trecho"}), 400

    db.collection("reservas").document(data["codigoReserva"]).set(data)
    return jsonify({"status": "ok", "id": data["codigoReserva"]}), 201


if __name__ == "__main__":
    app.run(debug=True)