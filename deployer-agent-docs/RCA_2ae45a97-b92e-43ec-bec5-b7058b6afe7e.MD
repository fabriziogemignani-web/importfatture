# RCA — fe-archivio redeploy failure (run 2ae45a97-b92e-43ec-bec5-b7058b6afe7e)

## Symptom
Redeploy failed at the `deploy_k8s` step: "deployment failed to become ready: timed out waiting for the condition". nginx logged repeated `connect() failed (111: Connection refused) ... upstream http://127.0.0.1:8001/health` and `Backend died, shutting down nginx`.

## Root cause (PROVEN)
The FastAPI backend crashes during startup. Traceback ends at:

```
File "/app/backend/server.py", line 690, in startup
    await db.anagrafiche.create_index([("company_vat", 1), ("ruolo", 1), ("chiave", 1)], unique=True)
pymongo.errors.DuplicateKeyError: E11000 duplicate key error collection:
  fe-archivio-test_database.anagrafiche index: company_vat_1_ruolo_1_chiave_1
  dup key: { company_vat: "01192570453", ruolo: "cliente", chiave: "01428910457" }
```

The new code (startup) builds a **unique** compound index on `(company_vat, ruolo, chiave)`, but the production `anagrafiche` collection already contains duplicates for that key. Because the crash happens in the FastAPI startup/lifespan event, the app never binds port 8001, so nginx cannot reach the backend, readiness never passes, and the k8s rollout times out.

### Evidence gathered
- `mongo_query count` on `anagrafiche` for `{company_vat:"01192570453", ruolo:"cliente", chiave:"01428910457"}` → **2** documents.
- `mongo_query find` on that key → two documents with **different `_id` but byte-identical content** (same denominazione "GAMMA SOFTWARE ...", same created_at 2026-10-20T09:41:37.932Z). Genuine duplicate rows.
- `mongo_query list_indexes` on `anagrafiche` → only `_id_` exists; the unique index `company_vat_1_ruolo_1_chiave_1` never built (confirms the build is failing, not already present).

### Why the migration doesn't save it
`split_anagrafiche()` (server.py:427) only touches docs where `ruolo` does NOT exist (`{"ruolo": {"$exists": False}}`). The two offending docs already have `ruolo: "cliente"` set (written by an earlier run), so the migration skips them and never collapses the duplicate. The unique index build then fails on the pre-existing dup.

## Fix required — NOT manifest, NOT infra
This is a code + data issue. Two parts:

1. **Code (E1):** Before `await db.anagrafiche.create_index([(company_vat,1),(ruolo,1),(chiave,1)], unique=True)` at server.py:690, add an idempotent de-duplication step that collapses existing duplicate `(company_vat, ruolo, chiave)` documents down to one (keep one `_id`, delete the rest; re-point any `invoices.controparte_id` referencing the dropped `_id` to the kept one, mirroring the re-point logic already in `split_anagrafiche`). Only after the collection is clean should the unique index be created. This makes startup safe against the duplicates already in prod and resilient to re-runs.
   - Alternatively (less safe): build the index non-unique, or wrap the create_index so a DuplicateKeyError is logged and does not kill startup — but that defeats the intended constraint and leaves the dup. Recommend the de-dup approach.

2. **Data (User, optional):** If preferred, the duplicate document in the prod `anagrafiche` collection can be removed manually so the unique index can build. Keep one of the two identical `cliente` records for company_vat `01192570453` / chiave `01428910457` and delete the other. (A code de-dup step is still recommended so this can't recur and so any other duplicate keys are handled too.)

## Note
No manifest change can fix this; the failure is in application startup logic against real data. Re-running the deploy unchanged will fail identically. After E1 lands the de-dup fix, redeploy.
