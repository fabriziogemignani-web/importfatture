# PRD – Archivio Fatture Elettroniche

## Original problem statement
crea un software che legga le fatture elettroniche in formato XML e che memorizzi i dati nel seguente modo. Anagrafica cliente o Fornitore , e memorizzi la fattura in modo sia ricercabile , Le fattura andranno divise in attive e passive e dovranno anche essere divise per anno e ordinate per numero di protocollo. In piu dovranno essere caricate anche in modo massivo

User choices: P.IVA aziendale in impostazioni (cedente = azienda -> attiva, altrimenti passiva); protocollo = Numero fattura XML; login email/password; upload XML, ZIP, P7M; vista leggibile + export CSV.

## Architecture
- FastAPI (server.py, fattura_parser.py) + MongoDB (users, settings, invoices, anagrafiche, login_attempts)
- JWT httpOnly cookies, admin seeded from .env, no signup
- P7M decoded with `openssl cms -nosigs -noverify`; ZIP recursive; natural sort key on numero
- React + shadcn, Plus Jakarta Sans, Italian UI

## User personas
- Titolare/contabile PMI italiana che archivia fatture SDI

## Implemented (2026-10-15)
- Login/logout/refresh, brute force lockout
- Impostazioni P.IVA aziendale
- Caricamento massivo (batch da 10 file, progress, esito per file, duplicati rilevati)
- Fatture attive/passive divise per anno, ordinate per protocollo (asc/desc), ricerca, paginazione, totale
- Dettaglio fattura leggibile + XML raw + download XML + eliminazione
- Anagrafiche clienti/fornitori auto-generate, dettaglio con totali e storico
- Export CSV (; separatore, decimali con virgola)
- Dashboard con KPI, grafico mensile, ultime fatture

## Implemented (2026-10-20)
- Caricamento da cartella: pulsante "Carica da cartella" (webkitdirectory) + drag&drop di cartelle con lettura ricorsiva delle sottocartelle; filtro automatico .xml/.p7m/.zip

## Implemented (2026-10-20) – Gestione utenti
- Ruoli Amministratore/Utente; pagina /utenti (solo admin): crea, cambia ruolo, attiva/disattiva, imposta password, elimina (protezione ultimo admin e auto-modifica)
- Recupero password via email (Emergent managed Resend): token hash sha256, scadenza 1h, monouso, max 3/h; invalidazione sessioni dopo cambio password
- Impostazioni modificabili solo da admin
- Anagrafiche: etichette anno, riepilogo n. anagrafiche/documenti/importo totale, conteggi per anno e per tipo (clienti=attive, fornitori=passive)
- Anagrafiche: ordinamento cliccando le intestazioni (ragione sociale, documenti, importo; asc/desc)
- Multi-P.IVA: ogni utente collegato a una P.IVA (companies), vede solo i dati della sua P.IVA; admin vede tutte con selettore in sidebar; fatture senza la P.IVA come cedente/cessionario scartate; indici unici per (company_vat, dedup_key) e (company_vat, chiave)
- Utenti collegabili a più P.IVA (company_vats) con selettore in sidebar; header non autorizzato -> 403; migrazione automatica company_vat -> company_vats
- Code review fixes: test secrets from env, parse_fattura split in sub-functions + type hints, stable React keys, Upload results component
- Fix dettaglio anagrafica: mostra solo fatture e totali del ruolo selezionato (fornitore=passive, cliente=attive) con switch ruolo se entrambi; export CSV filtrato
- Anagrafiche separate per ruolo: un'azienda che è sia cliente sia fornitore ha due schede distinte (indice unico company_vat+ruolo+chiave); migrazione automatica all'avvio che divide le schede unite e riassegna le fatture
- Fix deploy: dedup_anagrafiche() all'avvio unisce schede duplicate (company_vat, ruolo, chiave) e riassegna le fatture prima di creare l'indice unico
- Avvio robusto: se l'indice unico anagrafiche fallisce, ripete il dedup e in ultima istanza registra l'errore senza bloccare l'avvio
- Deploy readiness: dedup_anagrafiche ora non cancella (soft-merge: merged_into, ruoli [], chiave suffissata); CORS da CORS_ORIGINS
- CORS sicuro: con CORS_ORIGINS="*" le credenziali cross-origin sono disattivate (app same-origin); anagrafiche unite nascoste da lista e dettaglio
- Code review 2: useMemo sui context, costanti grafico, try/else in store_invoice, root inizializzato nel parser
- Elenco fatture: colonna "Tipo doc." con badge colorato (TD01 neutro, TD04 rosso, altri tipi colori diversi, tooltip con descrizione)
- Filtro tipo documento in Fatture Attive/Passive (select con tipi presenti e conteggi, anche nell'export CSV); endpoint /api/invoices/doc-types
- Security audit fixes: limiti upload (50 file/richiesta, 100MB/file, ZIP max 3 livelli, 5000 file, 20MB/file, 300MB totali), DTD/ENTITY rifiutati, CSV anti formula-injection, cookie SameSite=Lax (anti-CSRF)
- Upload: membri ZIP corrotti/cifrati -> errore per file (no 500); CSRF guard: header X-Requested-With obbligatorio su POST/PUT/PATCH/DELETE /api (axios lo invia sempre)
- ZIP: lettura in streaming a blocchi da 64KB con limite reale (anti zip-bomb con file_size falsificato)
- Export commercialista (/esporta): ZIP di XML attivi e passivi per periodo (preset mese/trimestre/anno o date libere), cartelle attive/ e passive/ + riepilogo.csv; endpoint GET /api/invoices/export-zip?dal&al&tipo; /api/invoices accetta dal/al

## Backlog
- P1: Riclassificazione fatture già caricate se cambia la P.IVA
- P1: Gestione utenti aggiuntivi da admin
- P2: Filtri per data/tipo documento, export PDF stile AdE, scadenzario pagamenti
