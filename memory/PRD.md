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

## Backlog
- P1: Riclassificazione fatture già caricate se cambia la P.IVA
- P1: Gestione utenti aggiuntivi da admin
- P2: Filtri per data/tipo documento, export PDF stile AdE, scadenzario pagamenti
