# Deploying FoHow Admin online

This app is now ready to deploy — `wsgi.py`, `Procfile`, and `gunicorn` are
already set up. I can't create accounts or click through a provider's
dashboard for you (that has to be done from your own login), but here's
exactly what to do, with the platform I'd actually recommend for this app
and why.

## The one thing that matters: persistence

This app stores everything in a single SQLite file (`fohow.db`). Some free
hosting tiers (Render's free web service, for example) run on **ephemeral
disks** — the filesystem resets to what's in your uploaded code every time
the app restarts or redeploys, silently wiping `fohow.db` back to empty.
That's fine for testing, dangerous for real business data.

**Recommendation: PythonAnywhere's free tier.** It gives persistent file
storage at no cost — your `fohow.db` survives restarts and redeploys. The
trade-off is a slightly more manual setup (upload via their web UI/console
instead of `git push`), which is worth it for data safety.

---

## Option A — PythonAnywhere (free, persistent, recommended)

1. Go to **pythonanywhere.com** and create a free "Beginner" account.
2. In the **Files** tab, create a folder, e.g. `fohow_app`, and upload
   every file from this project into it (`app.py`, `wsgi.py`, `schema.sql`,
   `requirements.txt`, and the `static/` folder with `index.html` inside).
   You can drag-and-drop or use their in-browser file upload.
3. Open a **Bash console** from the Dashboard and run:
   ```bash
   cd fohow_app
   pip install --user -r requirements.txt
   ```
4. Go to the **Web** tab → **Add a new web app** → choose **Manual
   configuration** → pick your Python version (3.10 or newer).
5. In the **Code** section of that Web tab:
   - Set **Source code** to `/home/YOURUSERNAME/fohow_app`
   - Click the **WSGI configuration file** link it gives you, delete
     everything in it, and replace the last few lines with:
     ```python
     import sys
     path = '/home/YOURUSERNAME/fohow_app'
     if path not in sys.path:
         sys.path.append(path)
     from wsgi import application
     ```
     (Replace `YOURUSERNAME` with your actual PythonAnywhere username, and
     use the same path you used in step 4.)
6. Hit the big green **Reload** button at the top of the Web tab.
7. Your app is now live at `https://YOURUSERNAME.pythonanywhere.com` —
   open it and it should look and work exactly like it did locally.

`fohow.db` will be created automatically inside `fohow_app/` the first
time the app runs, and will persist across reloads, restarts, and code
updates, since PythonAnywhere's disk is not ephemeral.

---

## Option B — Render (free, but read the caveat first)

Render is the fastest "connect GitHub and go" option, but on the **free**
web service tier the disk is ephemeral (see above) — every redeploy or
periodic restart resets `fohow.db` to empty. Only use this if you're okay
with that, or if you upgrade to Render's paid **persistent disk** add-on.

1. Push this project to a GitHub repo (github.com → New repository →
   upload these files, or `git init && git add . && git commit && git
   push` from your machine).
2. Go to **render.com**, sign up, click **New → Web Service**, and connect
   that GitHub repo.
3. Configure:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
4. Deploy. Render gives you a URL like `https://your-app.onrender.com`.
5. **To make data persist:** in the service's **Disks** tab, add a
   persistent disk (small, low monthly cost) mounted at, say, `/data`, and
   change `DB_PATH` at the top of `app.py` to point there
   (`DB_PATH = "/data/fohow.db"`) before deploying.

---

## Set your login credentials before deploying

Run `python3 set_password.py "your-password"` locally first (see
`README.md`), then set the three printed values (`ADMIN_USERNAME`,
`ADMIN_PASSWORD_HASH`, `SECRET_KEY`) as environment variables on whichever
platform you use:

- **PythonAnywhere:** Web tab → "Environment variables" section.
- **Render:** your service → Environment tab → "Add Environment Variable".

Don't skip `SECRET_KEY` — without it, everyone gets logged out every time
the app restarts.
