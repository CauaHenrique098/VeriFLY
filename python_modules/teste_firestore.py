from firebase_db import db

doc_ref = db.collection("teste2").document("primeiro")

doc_ref.set({
    "nome": "João da Silva",
    "codigoReserva": "RES123456",
    "telefone": "34999999999",
    "pasta": "0042"
})

print("Dados gravados com sucesso!")