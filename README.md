# FoHow Natural Solutions — Admin App (connected to SQLite)

This is your original admin panel (`static/index.html` — same look, same
buttons, nothing redesigned) now wired to a real SQLite database through a
small Python backend, instead of the browser's `localStorage`. Data now
persists properly, can be backed up as a single file, and can be shared by
a team instead of living on one device.

## Run it

Requires Python 3.9+ (nothing else — SQLite support is built into Python).

```bash
cd fohow_app
pip install -r requirements.txt
python3 app.py
```

Then open **http://localhost:5000** in your browser. That's it — the
database file `fohow.db` is created automatically next to `app.py` the
first time you run it, and every Add/Edit/Delete/Promote/Pay action in the
UI now writes straight to that file.

Stop the server any time with `Ctrl+C`. Your data is safe in `fohow.db` —
just run `python3 app.py` again to pick up where you left off.

## Logging in

The app now has a login screen in front of everything, including the API.

**Default login (local testing only): `admin` / `changeme123`**

Before you show this to anyone else — and definitely before deploying it
publicly — set a real password:

```bash
python3 set_password.py "your-new-password"
```

This prints three lines like:

```
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=scrypt:32768:8:1$....
SECRET_KEY=0dd7560....
```

Set those as actual environment variables before starting the server, e.g.:

```bash
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD_HASH='scrypt:32768:8:1$....'
export SECRET_KEY='0dd7560....'
python3 app.py
```

(On PythonAnywhere/Render/etc. there's a dedicated "Environment variables"
section in their dashboard instead of `export` — see `DEPLOY.md`.)

`SECRET_KEY` should stay the same across restarts, or everyone gets logged
out each time you redeploy. If you don't set one, the app makes up a
random one every time it starts.

## What changed vs. the original file

- **Nothing visual.** Every screen, button, badge, and modal is identical.
- **Data layer only.** The old `load()`/`save()` functions that read/wrote
  `localStorage` were replaced with `fetch()` calls to a REST API
  (`/api/students`, `/api/distributors`, `/api/clients`, `/api/sales`,
  `/api/resources`) served by `app.py`.
- **Auto-qualification (500+ PV → Qualified Distributor)** now happens as a
  database trigger instead of client-side JavaScript, so it's enforced
  consistently no matter what adds the points.
- Everything else — search, filters, the Points/Pay/Detail modals, the
  Excel export buttons — works exactly as before, just against real data.

## Files

| File | Purpose |
|---|---|
| `app.py` | Flask server: login gate, UI, and `/api/*` endpoints |
| `set_password.py` | Run once to generate a real password + secret key |
| `wsgi.py` | Entry point for hosts that expect a WSGI `application` object |
| `Procfile` | Start command for Render/Railway-style hosts |
| `schema.sql` | Same database schema as the standalone database package |
| `static/index.html` | Your original admin UI, with only the data-loading/saving code changed |
| `fohow.db` | Created automatically on first run — your live data |
| `requirements.txt` | Flask, Werkzeug (password hashing), gunicorn |

## Backing up / moving your data

`fohow.db` is the entire database in one file. To back up, copy it
somewhere safe. To move to another computer, copy `fohow.db` alongside
`app.py`, `schema.sql`, and `static/` and run `python3 app.py` there.

## Multiple people using it at once

Right now this runs on one machine and is reachable at `localhost:5000`
from that machine only. To let others on the same office network connect,
they can browse to `http://<your-computer's-IP>:5000` while the server is
running. For a permanently-online, multi-location setup, this same
`app.py`/`schema.sql` pair can be deployed to a small free-tier host
(e.g. Render, Railway, Fly.io) — happy to help with that step if you want
to take it there.
