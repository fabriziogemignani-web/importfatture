# Iteration 9: prod DuplicateKeyError repro + legacy doc with existing unique index. Usage: python ... seedA|seedB|verifyA|verifyB|snapshot|cleanup
import json
import os
import sys
from datetime import datetime, timezone
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
VAT, DUP = "01192570453", "01428910457"
IDX = "company_vat_1_ruolo_1_chiave_1"


def inv(tipo, num, cid, tot):
    return {"company_vat": VAT, "tipo": tipo, "anno": 2025, "numero": num, "numero_key": num.zfill(10), "data": "2025-03-01",
            "totale": tot, "imposta": 0, "controparte_id": str(cid), "controparte_nome": "TEST_Dup", "controparte_piva": DUP,
            "dedup_key": f"TEST|{VAT}|{num}", "tipo_documento": "TD01", "filename": f"{num}.xml",
            "created_at": datetime.now(timezone.utc)}


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    return bool(cond)


def seed_a():
    cleanup()
    db.anagrafiche.drop_indexes()
    db.companies.insert_one({"_id": VAT, "name": "TEST_Prod Repro", "created_at": datetime.now(timezone.utc)})
    base = {"company_vat": VAT, "ruolo": "cliente", "ruoli": ["cliente"], "chiave": DUP, "denominazione": "TEST_Dup"}
    a1, a2 = ObjectId(), ObjectId()
    db.anagrafiche.insert_many([{"_id": a1, **base}, {"_id": a2, **base}])
    db.invoices.insert_many([inv("attiva", "A1", a1, 100.0), inv("attiva", "A2", a2, 50.5)])
    print("seedA", a1, a2, "indexes:", list(db.anagrafiche.index_information()))


def verify_a():
    ok = check(IDX in db.anagrafiche.index_information() and db.anagrafiche.index_information()[IDX].get("unique"), "unique index exists")
    d = list(db.anagrafiche.find({"company_vat": VAT, "chiave": DUP}))
    ok &= check(len(d) == 1 and d[0]["ruolo"] == "cliente", f"merged to 1 cliente ({len(d)})")
    ids = {i["controparte_id"] for i in db.invoices.find({"company_vat": VAT})}
    ok &= check(d and ids == {str(d[0]["_id"])}, f"both invoices -> kept id {ids}")
    print("RESULT", "OK" if ok else "FAILED")


def seed_b():
    assert IDX in db.anagrafiche.index_information(), "index must exist before seedB"
    leg = ObjectId()
    db.anagrafiche.insert_one({"_id": leg, "company_vat": VAT, "ruoli": ["cliente", "fornitore"], "chiave": DUP,
                               "denominazione": "TEST_Dup"})
    db.invoices.insert_many([inv("attiva", "L1", leg, 200.0), inv("passiva", "L2", leg, 300.0)])
    print("seedB legacy", leg, "index present:", IDX in db.anagrafiche.index_information())


def verify_b():
    ok = check(IDX in db.anagrafiche.index_information() and db.anagrafiche.index_information()[IDX].get("unique"), "unique index exists")
    ok &= check(db.anagrafiche.count_documents({"ruolo": {"$exists": False}}) == 0, "no docs without ruolo")
    rs = list(db.anagrafiche.find({"company_vat": VAT, "chiave": DUP}))
    by = {}
    for a in rs:
        by.setdefault(a["ruolo"], []).append(a)
    ok &= check(len(rs) == 2 and len(by.get("cliente", [])) == 1 and len(by.get("fornitore", [])) == 1,
                f"1 cliente + 1 fornitore ({[a['ruolo'] for a in rs]})")
    for a in rs:
        ok &= check(a["ruoli"] == [a["ruolo"]], f"{a['ruolo']} ruoli consistent")
    for i in db.invoices.find({"company_vat": VAT}):
        exp = by.get("cliente" if i["tipo"] == "attiva" else "fornitore", [None])[0]
        ok &= check(exp and i["controparte_id"] == str(exp["_id"]), f"invoice {i['numero']} ({i['tipo']}) -> {exp and exp['ruolo']}")
    print("RESULT", "OK" if ok else "FAILED")


def snapshot():
    a = sorted((str(x["_id"]), x.get("ruolo"), tuple(x.get("ruoli", []))) for x in db.anagrafiche.find({"company_vat": VAT}))
    i = sorted((x["numero"], x["controparte_id"]) for x in db.invoices.find({"company_vat": VAT}))
    print(json.dumps({"anag": a, "inv": i, "idx": sorted(db.anagrafiche.index_information())}))


def cleanup():
    db.invoices.delete_many({"company_vat": VAT})
    db.anagrafiche.delete_many({"company_vat": VAT})
    db.companies.delete_many({"_id": VAT})
    print("cleaned; companies:", db.companies.count_documents({}), "anag:", db.anagrafiche.count_documents({}),
          "inv:", db.invoices.count_documents({}))


{"seedA": seed_a, "verifyA": verify_a, "seedB": seed_b, "verifyB": verify_b, "snapshot": snapshot, "cleanup": cleanup}[sys.argv[1]]()
