# Repro of prod DuplicateKeyError on anagrafiche unique index: seed (python dedup_repro.py seed) / verify / cleanup
import os
import sys
from datetime import datetime, timezone
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
VAT, VAT2 = "01192570453", "09999999990"
DUP, LEG, MIX = "01428910457", "02222222222", "03333333333"
IDS = {}


def inv(vat, tipo, num, cid, piva, tot):
    return {"company_vat": vat, "tipo": tipo, "anno": 2025, "numero": num, "numero_key": num.zfill(10), "data": "2025-03-01",
            "totale": tot, "imposta": 0, "controparte_id": str(cid), "controparte_nome": f"TEST_{piva}",
            "controparte_piva": piva, "dedup_key": f"TEST|{vat}|{num}", "tipo_documento": "TD01", "filename": f"{num}.xml",
            "created_at": datetime.now(timezone.utc)}


def seed():
    cleanup()
    db.anagrafiche.drop_indexes()
    now = datetime.now(timezone.utc)
    db.companies.insert_many([{"_id": VAT, "name": "TEST_Prod Repro", "created_at": now},
                              {"_id": VAT2, "name": "TEST_Other", "created_at": now}])
    base = {"company_vat": VAT, "ruolo": "cliente", "ruoli": ["cliente"], "chiave": DUP, "denominazione": "TEST_Dup Cliente Srl"}
    a1, a2, a3 = ObjectId(), ObjectId(), ObjectId()
    db.anagrafiche.insert_many([{"_id": a1, **base}, {"_id": a2, **base}, {"_id": a3, **base}])  # triple dup
    other = ObjectId()  # same chiave in other company -> must NOT be merged
    db.anagrafiche.insert_one({"_id": other, **{**base, "company_vat": VAT2}})
    leg = ObjectId()
    db.anagrafiche.insert_one({"_id": leg, "company_vat": VAT, "ruoli": ["cliente", "fornitore"], "chiave": LEG,
                               "denominazione": "TEST_Legacy Srl"})
    mix_c, mix_leg = ObjectId(), ObjectId()  # existing cliente + legacy doc for same chiave -> split then dedup
    db.anagrafiche.insert_one({"_id": mix_c, "company_vat": VAT, "ruolo": "cliente", "ruoli": ["cliente"], "chiave": MIX,
                               "denominazione": "TEST_Mix Srl"})
    db.anagrafiche.insert_one({"_id": mix_leg, "company_vat": VAT, "ruoli": ["fornitore", "cliente"], "chiave": MIX,
                               "denominazione": "TEST_Mix Srl"})
    db.invoices.insert_many([
        inv(VAT, "attiva", "D1", a1, DUP, 100.0), inv(VAT, "attiva", "D2", a2, DUP, 50.5), inv(VAT, "attiva", "D3", a3, DUP, 10.0),
        inv(VAT2, "attiva", "O1", other, DUP, 7.0),
        inv(VAT, "attiva", "L1", leg, LEG, 200.0), inv(VAT, "passiva", "L2", leg, LEG, 300.0),
        inv(VAT, "attiva", "M1", mix_c, MIX, 11.0), inv(VAT, "attiva", "M2", mix_leg, MIX, 22.0), inv(VAT, "passiva", "M3", mix_leg, MIX, 33.0),
    ])
    print("seeded", dict(a1=a1, a2=a2, a3=a3, other=other, leg=leg, mix_c=mix_c, mix_leg=mix_leg))


def verify():
    ok = True

    def check(cond, msg):
        nonlocal ok
        ok &= bool(cond)
        print(("PASS " if cond else "FAIL ") + msg)

    idx = db.anagrafiche.index_information()
    check("company_vat_1_ruolo_1_chiave_1" in idx and idx["company_vat_1_ruolo_1_chiave_1"].get("unique"), "unique index exists")
    check(db.anagrafiche.count_documents({"ruolo": {"$exists": False}}) == 0, "no docs without ruolo")
    d = list(db.anagrafiche.find({"company_vat": VAT, "chiave": DUP}))
    check(len(d) == 1 and d[0]["ruolo"] == "cliente", f"DUP merged to 1 ({len(d)})")
    if d:
        ids = {i["controparte_id"] for i in db.invoices.find({"company_vat": VAT, "controparte_piva": DUP})}
        check(ids == {str(d[0]["_id"])}, f"DUP invoices repointed {ids}")
    o = list(db.anagrafiche.find({"company_vat": VAT2, "chiave": DUP}))
    check(len(o) == 1 and db.invoices.find_one({"company_vat": VAT2})["controparte_id"] == str(o[0]["_id"]), "other company untouched")
    for ch in (LEG, MIX):
        rs = {a["ruolo"]: a for a in db.anagrafiche.find({"company_vat": VAT, "chiave": ch})}
        check(sorted(rs) == ["cliente", "fornitore"] and db.anagrafiche.count_documents({"company_vat": VAT, "chiave": ch}) == 2,
              f"{ch} -> cliente+fornitore {sorted(rs)}")
        for a in rs.values():
            check(a["ruoli"] == [a["ruolo"]], f"{ch} {a['ruolo']} ruoli consistent")
        for i in db.invoices.find({"company_vat": VAT, "controparte_piva": ch}):
            exp = rs.get("cliente" if i["tipo"] == "attiva" else "fornitore")
            check(exp and i["controparte_id"] == str(exp["_id"]), f"{ch} invoice {i['numero']} ({i['tipo']}) -> {exp and exp['ruolo']}")
    orphans = [i["numero"] for i in db.invoices.find({"company_vat": {"$in": [VAT, VAT2]}})
               if not db.anagrafiche.find_one({"_id": ObjectId(i["controparte_id"])})]
    check(not orphans, f"no orphan invoices {orphans}")
    print("SNAPSHOT", sorted((str(a["_id"]), a["chiave"], a["ruolo"]) for a in db.anagrafiche.find({"company_vat": {"$in": [VAT, VAT2]}})))
    print("ALL OK" if ok else "SOME FAILED")


def cleanup():
    db.invoices.delete_many({"company_vat": {"$in": [VAT, VAT2]}})
    db.anagrafiche.delete_many({"company_vat": {"$in": [VAT, VAT2]}})
    db.companies.delete_many({"_id": {"$in": [VAT, VAT2]}})


if __name__ == "__main__":
    {"seed": seed, "verify": verify, "cleanup": cleanup}[sys.argv[1]]()
