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

## Backlog
- P1: Riclassificazione fatture già caricate se cambia la P.IVA
- P1: Gestione utenti aggiuntivi da admin
- P2: Filtri per data/tipo documento, export PDF stile AdE, scadenzario pagamenti
