"""Testes do fluxo sem credenciais, navegador ou chamadas ao Firestore real."""

import copy
import importlib
import sys
import types
import unittest
from datetime import timedelta
from unittest.mock import patch


class Snapshot:
    def __init__(self, ref):
        self.reference = ref
        self.id = ref.id
        self.data = copy.deepcopy(ref.store.get(ref.key))
        self.exists = self.data is not None

    def to_dict(self):
        return copy.deepcopy(self.data)


class Reference:
    def __init__(self, store, collection, doc_id):
        self.store, self.id = store, doc_id
        self.key = collection, doc_id

    def get(self, transaction=None):
        return Snapshot(self)

    def update(self, data):
        self.store[self.key].update(copy.deepcopy(data))


class Collection:
    def __init__(self, store, name):
        self.store, self.name = store, name
        self.filter = None

    def document(self, doc_id):
        return Reference(self.store, self.name, doc_id)

    def where(self, *, filter):
        self.filter = filter
        return self

    def stream(self):
        for collection, doc_id in list(self.store):
            if collection == self.name:
                snapshot = self.document(doc_id).get()
                if self.filter is None or snapshot.data.get(self.filter.field_path) == self.filter.value:
                    yield snapshot


class Transaction:
    def set(self, ref, data):
        ref.store[ref.key] = copy.deepcopy(data)

    def update(self, ref, data):
        ref.update(data)


class Database:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return Collection(self.store, name)

    def transaction(self):
        return Transaction()

    def get_all(self, refs):
        return [ref.get() for ref in refs]


class LocalVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Importar o servidor também deve funcionar sem o Playwright instalado.
        firebase_stub = types.ModuleType("firebase_db")
        firebase_stub.db = Database()
        previous_firebase = sys.modules.get("firebase_db")
        previous_playwright = sys.modules.get("playwright")
        sys.modules["firebase_db"] = firebase_stub
        sys.modules["playwright"] = None
        try:
            cls.queue = importlib.import_module("verification_queue")
            cls.app_module = importlib.import_module("app")
            cls.comparator = importlib.import_module("comparator")
        finally:
            for name, previous in (("firebase_db", previous_firebase), ("playwright", previous_playwright)):
                if previous is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = previous

    def setUp(self):
        self.db = Database()
        self.db.store["reservas", "ABC123"] = {
            "name": "Teste", "status": "pending", "codeReserve": "ABC123",
            "stretches": [{"company": "azul", "origin": "UDI", "destination": "MCZ",
                           "departureOriginal": "2027-05-23T12:55", "urlReserve": "https://example.test/reserva"}],
        }
        for target in (self.queue, self.app_module, self.comparator):
            patcher = patch.object(target, "db", self.db)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(self.queue.firestore, "transactional", lambda fn: fn)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = self.app_module.app.test_client()

    def start_check(self):
        self.queue.request_check("ABC123")
        claim = self.queue.claim_next()
        return claim[1], copy.deepcopy(self.db.store["reservas", "ABC123"])

    def test_api_enqueues_without_importing_or_running_playwright(self):
        with patch.dict(sys.modules, {"playwright": None, "flight_search": None}):
            response = self.client.post("/api/reservas/ABC123/comparar")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json["verification"]["state"], "queued")
        self.assertNotIn("lastCheck", self.db.store["reservas", "ABC123"])

    def test_missing_reserve_returns_404(self):
        self.assertEqual(self.client.post("/api/reservas/missing/comparar").status_code, 404)
        self.assertNotIn(("verificacoes", "missing"), self.db.store)

    def test_duplicate_request_preserves_running_job(self):
        token, _ = self.start_check()
        self.queue.request_check("ABC123")
        self.assertEqual(self.db.store["verificacoes", "ABC123"]["token"], token)
        self.assertIsNone(self.queue.claim_next())

    def test_expired_job_reclaimed_and_old_worker_rejected(self):
        old_token, reserve = self.start_check()
        self.db.store["verificacoes", "ABC123"]["leaseUntil"] = self.queue.now() - timedelta(seconds=1)
        _, new_token = self.queue.claim_next()
        self.assertNotEqual(old_token, new_token)
        self.assertFalse(self.queue.finish_check("ABC123", old_token, reserve, {"status": "confirmed"}))
        self.assertEqual(self.db.store["reservas", "ABC123"]["status"], "pending")
        self.assertTrue(self.queue.renew_lease("ABC123", new_token))
        self.assertFalse(self.queue.renew_lease("ABC123", old_token))

    def test_result_published_and_visible_on_dashboard(self):
        token, reserve = self.start_check()
        self.queue.finish_check("ABC123", token, reserve, {"status": "confirmed", "lastCheckError": None})
        response = self.client.get("/api/reservas")
        self.assertEqual(response.json[0]["status"], "confirmed")
        self.assertEqual(response.json[0]["verification"]["state"], "done")
        self.assertNotIn("token", response.json[0]["verification"])
        self.queue.request_check("ABC123")
        self.assertEqual(self.db.store["verificacoes", "ABC123"]["state"], "queued")

    def test_manual_status_wins_over_late_result(self):
        for status in ("solved", "completed"):
            with self.subTest(status=status):
                self.db.store["reservas", "ABC123"]["status"] = "pending"
                token, reserve = self.start_check()
                self.db.store["reservas", "ABC123"]["status"] = status
                self.queue.finish_check("ABC123", token, reserve, {"status": "confirmed"})
                self.assertEqual(self.db.store["reservas", "ABC123"]["status"], status)
                self.assertEqual(self.db.store["verificacoes", "ABC123"]["state"], "skipped")

    def test_edited_stretches_trigger_new_search(self):
        token, reserve = self.start_check()
        self.db.store["reservas", "ABC123"]["stretches"][0]["departureOriginal"] = "2027-05-24T12:55"
        self.assertFalse(self.queue.finish_check("ABC123", token, reserve, {"status": "confirmed"}))
        self.assertEqual(self.db.store["verificacoes", "ABC123"]["state"], "queued")
        self.assertEqual(self.db.store["reservas", "ABC123"]["status"], "pending")

    def test_failed_search_preserves_reserve_status(self):
        token, reserve = self.start_check()
        search = types.ModuleType("flight_search")
        search.search_flight = lambda *args: {"outbound_flight_infos": {"origin": {"date": None}}}
        with patch.dict(sys.modules, {"flight_search": search}):
            update = self.comparator.build_comparison_update(reserve)
        self.queue.finish_check("ABC123", token, reserve, update)
        self.assertEqual(self.db.store["reservas", "ABC123"]["status"], "pending")
        self.assertEqual(self.db.store["verificacoes", "ABC123"]["state"], "failed")
        self.assertIn("não retornou", self.db.store["reservas", "ABC123"]["lastCheckError"])

    def test_local_worker_searches_and_publishes(self):
        token, _ = self.start_check()
        search = types.ModuleType("flight_search")
        search.search_flight = lambda *args: {"outbound_flight_infos": {
            "origin": {"airport": "UDI", "date": "23/05/2027", "hour": "12:55"},
            "destiny": {"airport": "MCZ", "date": "23/05/2027", "hour": "15:30"},
        }}
        firebase_stub = types.ModuleType("firebase_db")
        firebase_stub.db = self.db
        with patch.dict(sys.modules, {"firebase_db": firebase_stub, "flight_search": search}):
            import local_worker
            local_worker.process_check("ABC123", token)
        self.assertEqual(self.db.store["reservas", "ABC123"]["status"], "confirmed")
        self.assertEqual(self.db.store["verificacoes", "ABC123"]["state"], "done")

    def test_completed_reserve_is_not_enqueued(self):
        self.db.store["reservas", "ABC123"]["status"] = "completed"
        response = self.client.post("/api/reservas/ABC123/comparar")
        self.assertEqual(response.status_code, 202)
        self.assertNotIn(("verificacoes", "ABC123"), self.db.store)


if __name__ == "__main__":
    unittest.main()
