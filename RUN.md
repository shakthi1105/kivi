# RUN.md

**Primary review method: a completely local application (SQLite embedded, no network calls, no LLM/API key required).**

No LLM key is needed anywhere in this system — matching is deterministic
(Metaphone phonetic keys + SQLite), so there is no `.env` / `.env.example` to
configure. See README.md §2 and §5 for why.

---

## 1. Runtimes and versions

- Python 3.11 or later (developed and tested on 3.12.3)
- `pip` for installing dependencies (see `requirements.txt`)
- No database server, Docker, or Node.js required

## 2. Required environment variables

None are required. One optional variable:

- `KIVI_DB_PATH` — path to the SQLite file. Defaults to `./data/kivi.db`
  (created automatically, including the `data/` directory, on first run).

## 3. Install dependencies

From the repository root:

```bash
pip install -r requirements.txt
```

(If your environment requires it: `pip install -r requirements.txt --break-system-packages`.)

## 4. Create, migrate, and seed the database

The schema is created automatically and idempotently (`CREATE TABLE IF NOT
EXISTS`) the first time the app touches the database — there is no separate
migration tool. To create the schema **and** load a small, reproducible set
of seed observations in one step:

```bash
python3 scripts/seed.py
```

This resets any existing state first, then adds 9 observations forming 4
memory entries (a person's name, a teammate's name, a context-scoped product
term, and a tool name) — so the demo UI is populated immediately instead of
starting empty. Expected output ends with:

```
Seeded 9 observations.
  'Aaditya'       key=ATTY   ctx=None  obs=2  conf=1.00
  'Figma'         key=FKM    ctx=None  obs=2  conf=1.00
  'Kivi'          key=KW     ctx=sarvam  obs=3  conf=1.00
  'Nehal'         key=NHL    ctx=None  obs=2  conf=1.00
```

## 5. Start the process

```bash
python3 -m uvicorn app.main:app --port 8000
```

This is the only process required — the API and the static demo UI are
served by the same FastAPI app.

## 6. Interface to open

```
http://127.0.0.1:8000/
```

## 7. Primary interactions to try

1. **Inspect memory** — section 2 of the page already shows the 4 seeded
   entries (click "Refresh" if you seeded after the page loaded).
2. **Feed the brief's exact example** — in section 3, paste:
   - ASR output: `ask aditya to review the sarvam kiwi service`
   - Formatted output: `Ask Aditya to review the Sarvam Kiwi service.`

   Click Resolve. Expected memory-aware output:
   `Ask Aaditya to review the Sarvam Kivi service.` The token trace below it
   shows why each word was or wasn't changed.
3. **Show the context-scoping protection** — resolve
   `I had a kiwi for breakfast.` and note "kiwi" is left untouched (no
   "sarvam" before it), even though the same phonetic memory entry exists.
4. **Teach a new correction live** — in section 1, add an observation (e.g.
   heard `rohit`, corrected `Rohith`) once, then resolve a sentence
   containing "Rohit" — nothing changes yet (below the 2-observation
   minimum). Add the same observation a second time, resolve again — it now
   applies. This demonstrates evidence accumulating in real time.
5. **Reset** — the button in the header wipes all observations and memory
   entries; section 2 and section 4 (raw observation log) go empty
   immediately.

## 8. Run the evaluation

```bash
python3 eval/run_eval.py
```

This uses its own database at `data/eval.db`, independent of whatever state
you built up manually in step 7, and does not require the server (step 5) to
be running.

For the unit-test layer:

```bash
python3 -m pytest tests/ -q
```

## 9. Where evaluation results are written

- `eval/results.json` — full machine-readable detail per case (inputs,
  expected/actual output, memory state, full reasoning trace, latency).
- `eval/report.md` — human-readable summary with the same information.

The versions of these two files already committed in this repository are the
literal output of the last run of `eval/run_eval.py` against the committed
code (not hand-edited).

## 10. Resetting the system

Any of the following works:

- Click "Reset system" in the demo UI (calls `POST /api/reset`).
- `curl -X POST http://127.0.0.1:8000/api/reset`
- Delete the database file entirely and re-seed:
  ```bash
  rm -rf data/
  python3 scripts/seed.py
  ```
