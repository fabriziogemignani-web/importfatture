# Iteration 9: startup safeguard - anagrafiche unique index build failing twice must not crash startup; regression via public URL
import asyncio
import os
import sys
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
VAT, DUP = "01192570453", "01428910457"
sys.path.insert(0, "/app/backend")


# Fallback path: create_index raises DuplicateKeyError on every attempt -> startup() logs and completes
def test_startup_survives_persistent_duplicate_key(caplog):
    from motor.motor_asyncio import AsyncIOMotorCollection
    from pymongo.errors import DuplicateKeyError
    import server

    orig = AsyncIOMotorCollection.create_index
    calls = []

    async def fake(self, keys, *a, **kw):
        if self.name == "anagrafiche" and isinstance(keys, list) and ("ruolo", 1) in keys:
            calls.append(keys)
            raise DuplicateKeyError("E11000 simulated")
        return await orig(self, keys, *a, **kw)

    AsyncIOMotorCollection.create_index = fake
    try:
        async def run():
            server.client.get_io_loop = asyncio.get_running_loop
            await server.startup()
        asyncio.run(run())
    finally:
        AsyncIOMotorCollection.create_index = orig
    assert len(calls) == 2, f"expected initial attempt + 1 retry, got {len(calls)}"
    assert "Unique index on anagrafiche not built" in caplog.text


# Regression: admin login + clienti list for prod company shows one combined row
@pytest.fixture(scope="module")
def s():
    from dotenv import dotenv_values
    env = dotenv_values("/app/backend/.env")
    sess = requests.Session()
    r = sess.post(f"{BASE_URL}/api/auth/login", json={"email": env["ADMIN_EMAIL"], "password": env["ADMIN_PASSWORD"]})
    assert r.status_code == 200, r.text
    assert "access_token" in r.cookies or any("token" in c.name for c in sess.cookies)
    return sess


def test_me(s):
    r = s.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 200 and r.json()["role"] == "admin"


def test_clienti_single_row_combined(s):
    r = s.get(f"{BASE_URL}/api/anagrafiche", params={"ruolo": "cliente"}, headers={"X-Company-Vat": VAT})
    assert r.status_code == 200, r.text
    rows = [a for a in r.json() if a["chiave"] == DUP]
    assert len(rows) == 1, rows
    assert rows[0]["n_fatture"] == 3 and rows[0]["totale_fatture"] == 350.5, rows[0]


def test_fornitori_single_row(s):
    r = s.get(f"{BASE_URL}/api/anagrafiche", params={"ruolo": "fornitore"}, headers={"X-Company-Vat": VAT})
    rows = [a for a in r.json() if a["chiave"] == DUP]
    assert len(rows) == 1 and rows[0]["n_fatture"] == 1 and rows[0]["totale_fatture"] == 300.0, rows
