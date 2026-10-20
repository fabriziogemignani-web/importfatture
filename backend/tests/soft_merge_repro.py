# Repro of startup soft-merge dedup (no deletes): python soft_merge_repro.py seed|verify|snapshot|cleanup  (LOCAL DB only)
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
STATE = "/tmp/soft_merge_ids.json"


def inv(num, cid, tot):
    return {"company_vat": VAT, "tipo": "attiva", "anno": 2025, "numero": num, "numero_key": num.zfill(10), "data": "2025-03-01",
            "totale": tot, "imposta": 0, "imponibile": tot, "controparte_id": str(cid), "controparte_nome": "TEST_Dup",
            "controparte_piva": DUP, "dedup_key": f"TEST|{VAT}|{num}", "tipo_documento": "TD01", "filename": f"{num}.xml",
            "xml": "<x/>", "created_at": datetime.now(timezone.utc)}


def seed():
    cleanup()
    db.anagrafiche.drop_indexes()
    db.companies.insert_one({"_id": VAT, "name": "TEST_SoftMerge", "created_at": datetime.now(timezone.utc)})
    base = {"company_vat": VAT, "ruolo": "cliente", "ruoli": ["cliente"], "chiave": DUP, "denominazione": "TEST_Dup"}
    a1, a2 = ObjectId(), ObjectId()
    db.anagrafiche.insert_many([{"_id": a1, **base}, {"_id": a2, **base}])
    db.invoices.insert_many([inv("SM1", a1, 100.0), inv("SM2", a2, 50.5)])
    json.dump({"a1": str(a1), "a2": str(a2)}, open(STATE, "w"))
    print("seeded", a1, a2, "indexes:", list(db.anagrafiche.index_information()))


def snapshot():
    return sorted((str(a["_id"]), a.get("chiave"), a.get("ruolo"), tuple(a.get("ruoli", [])), a.get("merged_into"))
                  for a in db.anagrafiche.find({"company_vat": VAT})) + \
        sorted((i["numero"], i["controparte_id"]) for i in db.invoices.find({"company_vat": VAT}))


def verify():
    ids = json.load(open(STATE))
    keep, dupe = sorted([ids["a1"], ids["a2"]])
    ok = True

    def check(c, m):
        nonlocal ok
        ok &= bool(c)
        print(("PASS " if c else "FAIL ") + m)

    check(db.anagrafiche.count_documents({"company_vat": VAT}) == 2, "anagrafiche count stays 2")
    active = list(db.anagrafiche.find({"company_vat": VAT, "ruoli": "cliente"}))
    check(len(active) == 1 and str(active[0]["_id"]) == keep, f"one active cliente = kept {keep}")
    m = db.anagrafiche.find_one({"_id": ObjectId(dupe)})
    check(m and m.get("merged_into") == keep and m.get("ruoli") == [] and m.get("ruolo") == "unita"
          and m.get("chiave") == f"{DUP}#unita#{dupe}", f"merged record fields {m and {k: m.get(k) for k in ('merged_into','ruoli','ruolo','chiave')}}")
    cids = {i["controparte_id"] for i in db.invoices.find({"company_vat": VAT})}
    check(cids == {keep}, f"both invoices -> kept {cids}")
    idx = db.anagrafiche.index_information().get("company_vat_1_ruolo_1_chiave_1")
    check(idx and idx.get("unique"), "unique index company_vat_1_ruolo_1_chiave_1 exists")
    print("SNAPSHOT", snapshot())
    print("ALL OK" if ok else "SOME FAILED")


def cleanup():
    db.invoices.delete_many({"company_vat": VAT})
    db.anagrafiche.delete_many({"company_vat": VAT})
    db.companies.delete_many({"_id": VAT})
    db.users.delete_many({"email": {"$regex": "^test_softmerge", "$options": "i"}})


if __name__ == "__main__":
    {"seed": seed, "verify": verify, "cleanup": cleanup, "snapshot": lambda: print(snapshot())}[sys.argv[1]]()
