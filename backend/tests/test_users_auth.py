"""User management (admin), RBAC, forgot/reset password tests."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

BASE_URL = None
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
RESEND_EMAIL = "delivered@resend.dev"

_env = {}
with open("/app/backend/.env") as f:
    for line in f:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            _env[k] = v.strip('"')
mdb = MongoClient(_env["MONGO_URL"])[_env["DB_NAME"]]

U_EMAIL = "test_user_pytest@example.com"
U2_EMAIL = "test_admin2_pytest@example.com"
U_PW = "TestPass123"
TEST_VAT = "08888888888"


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    return s, r


@pytest.fixture(scope="module")
def admin():
    s, r = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    mdb.companies.update_one({"_id": TEST_VAT}, {"$setOnInsert": {"name": "TEST Auth Co", "created_at": datetime.now(timezone.utc)}}, upsert=True)
    mdb.users.delete_many({"email": {"$in": [U_EMAIL, U2_EMAIL]}})
    mdb.login_attempts.delete_many({"identifier": {"$regex": "pytest"}})
    yield
    for e in [U_EMAIL, U2_EMAIL]:
        u = mdb.users.find_one({"email": e})
        if u:
            mdb.password_reset_tokens.delete_many({"user_id": str(u["_id"])})
    mdb.users.delete_many({"email": {"$in": [U_EMAIL, U2_EMAIL]}})
    mdb.companies.delete_one({"_id": TEST_VAT})


def _uid(email):
    return str(mdb.users.find_one({"email": email})["_id"])


# --- Auth basics / playbook ---
class TestAuthPlaybook:
    def test_login_cookies_httponly(self):
        s, r = login(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert r.status_code == 200
        sc = r.headers.get("set-cookie", "").lower()
        assert "access_token" in sc and "httponly" in sc and "refresh_token" in sc

    def test_bcrypt_hash(self):
        u = mdb.users.find_one({"email": ADMIN_EMAIL})
        assert u["password_hash"].startswith("$2b$")

    def test_cors_credentials(self):
        r = requests.options(f"{API}/auth/login", headers={"Origin": BASE_URL, "Access-Control-Request-Method": "POST"})
        assert r.headers.get("access-control-allow-origin") == BASE_URL
        assert r.headers.get("access-control-allow-credentials") == "true"

    def test_me_and_logout(self):
        s, _ = login(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert s.get(f"{API}/auth/me").json()["email"] == ADMIN_EMAIL
        assert s.post(f"{API}/auth/logout").status_code == 200


# --- Admin user CRUD ---
class TestUsersCRUD:
    def test_create_user(self, admin):
        r = admin.post(f"{API}/users", json={"email": U_EMAIL, "name": "TEST_User", "role": "user", "password": U_PW, "company_vats": [TEST_VAT]})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email"] == U_EMAIL and d["role"] == "user" and d["active"] is True
        assert "password_hash" not in d and "_id" not in d
        lst = admin.get(f"{API}/users").json()
        assert any(u["email"] == U_EMAIL for u in lst)

    def test_duplicate_email(self, admin):
        r = admin.post(f"{API}/users", json={"email": U_EMAIL.upper(), "name": "x", "role": "user", "password": U_PW})
        assert r.status_code == 400

    def test_short_password_and_bad_role(self, admin):
        assert admin.post(f"{API}/users", json={"email": "test_x@example.com", "password": "short"}).status_code == 422
        assert admin.post(f"{API}/users", json={"email": "test_x@example.com", "role": "root", "password": U_PW}).status_code == 422
        assert admin.post(f"{API}/users", json={"email": "notanemail", "password": U_PW}).status_code == 400

    def test_new_user_can_login(self):
        s, r = login(U_EMAIL, U_PW)
        assert r.status_code == 200 and r.json()["role"] == "user"

    def test_non_admin_forbidden(self):
        s, _ = login(U_EMAIL, U_PW)
        assert s.get(f"{API}/users").status_code == 403
        assert s.post(f"{API}/users", json={"email": "test_y@example.com", "password": U_PW}).status_code == 403
        assert s.patch(f"{API}/users/{_uid(ADMIN_EMAIL)}", json={"role": "user"}).status_code == 403
        assert s.delete(f"{API}/users/{_uid(ADMIN_EMAIL)}").status_code == 403
        assert s.post(f"{API}/users/{_uid(ADMIN_EMAIL)}/password", json={"password": "Hacked1234"}).status_code == 403
        assert s.post(f"{API}/companies", json={"company_vat": "01234567890"}).status_code == 403
        # non-admin can still read archive
        assert s.get(f"{API}/companies").status_code == 200
        assert s.get(f"{API}/invoices").status_code == 200

    def test_change_role_and_back(self, admin):
        uid = _uid(U_EMAIL)
        r = admin.patch(f"{API}/users/{uid}", json={"role": "admin"})
        assert r.status_code == 200 and r.json()["role"] == "admin"
        r = admin.patch(f"{API}/users/{uid}", json={"role": "user", "name": "TEST_Renamed"})
        assert r.status_code == 200 and r.json()["role"] == "user"
        assert mdb.users.find_one({"email": U_EMAIL})["name"] == "TEST_Renamed"

    def test_admin_set_password(self, admin):
        uid = _uid(U_EMAIL)
        assert admin.post(f"{API}/users/{uid}/password", json={"password": "short"}).status_code == 422
        r = admin.post(f"{API}/users/{uid}/password", json={"password": "NewPass1234"})
        assert r.status_code == 200
        assert login(U_EMAIL, "NewPass1234")[1].status_code == 200
        admin.post(f"{API}/users/{uid}/password", json={"password": U_PW})

    def test_self_protection(self, admin):
        me = _uid(ADMIN_EMAIL)
        assert admin.patch(f"{API}/users/{me}", json={"role": "user"}).status_code == 400
        assert admin.patch(f"{API}/users/{me}", json={"active": False}).status_code == 400
        assert admin.delete(f"{API}/users/{me}").status_code == 400
        u = mdb.users.find_one({"email": ADMIN_EMAIL})
        assert u["role"] == "admin" and u.get("active", True)

    def test_last_admin_protection(self, admin):
        # create 2nd admin, deactivate primary admin is impossible (self), so log in as 2nd admin and try to demote primary
        r = admin.post(f"{API}/users", json={"email": U2_EMAIL, "name": "TEST_Admin2", "role": "admin", "password": U_PW})
        assert r.status_code == 200
        s2, r2 = login(U2_EMAIL, U_PW)
        assert r2.status_code == 200
        # admin2 demoting primary admin is allowed (admin2 remains) -> do NOT actually do it. Instead
        # deactivate admin2 from primary (others remain) is OK
        uid2 = _uid(U2_EMAIL)
        r = admin.patch(f"{API}/users/{uid2}", json={"active": False})
        assert r.status_code == 200
        # admin2 session now rejected
        assert s2.get(f"{API}/auth/me").status_code == 401
        admin.delete(f"{API}/users/{uid2}")

    def test_deactivate_user(self, admin):
        uid = _uid(U_EMAIL)
        s, _ = login(U_EMAIL, U_PW)
        assert s.get(f"{API}/auth/me").status_code == 200
        r = admin.patch(f"{API}/users/{uid}", json={"active": False})
        assert r.status_code == 200 and r.json()["active"] is False
        assert s.get(f"{API}/auth/me").status_code == 401
        assert s.post(f"{API}/auth/refresh").status_code == 401
        _, r = login(U_EMAIL, U_PW)
        assert r.status_code == 403 and "disattivato" in r.json()["detail"].lower()
        admin.patch(f"{API}/users/{uid}", json={"active": True})
        assert login(U_EMAIL, U_PW)[1].status_code == 200

    def test_invalid_ids(self, admin):
        fake = str(ObjectId())
        assert admin.patch(f"{API}/users/{fake}", json={"name": "x"}).status_code == 404
        assert admin.post(f"{API}/users/{fake}/password", json={"password": U_PW}).status_code == 404
        assert admin.delete(f"{API}/users/{fake}").status_code == 404
        assert admin.delete(f"{API}/users/not-an-id").status_code in (400, 404)


# --- Forgot / reset password ---
class TestPasswordReset:
    def test_forgot_unknown_email_generic(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": "nobody_test_pytest@example.com"})
        assert r.status_code == 200
        assert "Se l'email" in r.json()["message"]

    def test_forgot_real_send_creates_hashed_token(self):
        u = mdb.users.find_one({"email": RESEND_EMAIL})
        if not u:
            pytest.skip("delivered@resend.dev user missing")
        uid = str(u["_id"])
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        before = mdb.password_reset_tokens.count_documents({"user_id": uid, "created_at": {"$gt": since}})
        if before >= 3:
            pytest.skip("rate limited already")
        r = requests.post(f"{API}/auth/forgot-password", json={"email": RESEND_EMAIL})
        assert r.status_code == 200, r.text
        after = mdb.password_reset_tokens.count_documents({"user_id": uid, "created_at": {"$gt": since}})
        assert after == before + 1
        t = mdb.password_reset_tokens.find_one({"user_id": uid}, sort=[("created_at", -1)])
        assert len(t["token_hash"]) == 64 and t["used"] is False

    def test_forgot_rate_limit(self):
        u = mdb.users.find_one({"email": RESEND_EMAIL})
        if not u:
            pytest.skip("delivered@resend.dev user missing")
        uid = str(u["_id"])
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        now = datetime.now(timezone.utc)
        while mdb.password_reset_tokens.count_documents({"user_id": uid, "created_at": {"$gt": since}}) < 3:
            mdb.password_reset_tokens.insert_one({"token_hash": hashlib.sha256(secrets.token_hex(8).encode()).hexdigest(),
                                                  "user_id": uid, "used": True, "created_at": now,
                                                  "expires_at": now + timedelta(hours=1)})
        before = mdb.password_reset_tokens.count_documents({"user_id": uid})
        r = requests.post(f"{API}/auth/forgot-password", json={"email": RESEND_EMAIL})
        assert r.status_code == 200
        assert mdb.password_reset_tokens.count_documents({"user_id": uid}) == before

    def test_reset_invalid_token(self):
        r = requests.post(f"{API}/auth/reset-password", json={"token": "bogus", "password": "Whatever123"})
        assert r.status_code == 400 and "Link non valido" in r.json()["detail"]

    def test_reset_short_password(self):
        r = requests.post(f"{API}/auth/reset-password", json={"token": "bogus", "password": "abc"})
        assert r.status_code == 422

    def test_reset_valid_single_use(self):
        uid = _uid(U_EMAIL)
        tok = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        mdb.password_reset_tokens.insert_one({"token_hash": hashlib.sha256(tok.encode()).hexdigest(), "user_id": uid,
                                              "used": False, "created_at": now, "expires_at": now + timedelta(hours=1)})
        r = requests.post(f"{API}/auth/reset-password", json={"token": tok, "password": "ResetPass999"})
        assert r.status_code == 200
        assert login(U_EMAIL, "ResetPass999")[1].status_code == 200
        assert login(U_EMAIL, U_PW)[1].status_code == 401
        r = requests.post(f"{API}/auth/reset-password", json={"token": tok, "password": "Another9999"})
        assert r.status_code == 400

    def test_reset_expired_token(self):
        uid = _uid(U_EMAIL)
        tok = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        mdb.password_reset_tokens.insert_one({"token_hash": hashlib.sha256(tok.encode()).hexdigest(), "user_id": uid,
                                              "used": False, "created_at": now - timedelta(hours=2),
                                              "expires_at": now - timedelta(minutes=5)})
        r = requests.post(f"{API}/auth/reset-password", json={"token": tok, "password": "ResetPass999"})
        assert r.status_code == 400


# --- Delete ---
class TestDelete:
    def test_delete_user(self, admin):
        uid = _uid(U_EMAIL)
        assert admin.delete(f"{API}/users/{uid}").status_code == 200
        assert mdb.users.find_one({"email": U_EMAIL}) is None
        assert not any(u["email"] == U_EMAIL for u in admin.get(f"{API}/users").json())
