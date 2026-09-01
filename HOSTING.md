# Host HIREBLOCK yourself (step by step)

You will host **two things**:

1. Frontend = a static webpage (`frontend/index.html`)
2. Backend = FastAPI that stores hashed accounts + issues JWTs

GitHub Pages can host (1). It cannot run (2). Use Render or Railway for the API.

---

## 0. What this build does

- Signup takes: first name, optional middle, last name, birth date, and one identifier (driver license, FEIN, SSN, or most recent address).
- Each field is normalized and SHA-256 hashed separately, then those hashes are hashed again. That final hash is the account secret.
- Username is derived from the hash (`pro-…` or `co-…`).
- Server stores **username + hash + user type only**. No raw PII.
- Login recomputes the hash from the same fields. Match = JWT.
- New accounts are **early access**. Public launch is **TBD**.

Use fake SSN/DL values until counsel reviews this.

---

## 1. Put the code in La Cosa Nostra (manual)

1. Unzip `hireblock-early-access.zip`.
2. Open the org: https://github.com/LaCosaNostra
3. Create a new **private** repo, e.g. `hireblock`.
4. Click **Add file → Upload files**.
5. Upload the folders so the repo looks like:

```
README.md
HOSTING.md
frontend/index.html
backend/main.py
backend/requirements.txt
```

6. Commit.

---

## 2. Run it on your Windows PC first

Install Python 3.11+ from python.org if needed. Check **Add Python to PATH**.

In Command Prompt:

```bat
cd path\to\hireblock\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set HIREBLOCK_SECRET=pick-a-long-random-string-now
set HIREBLOCK_PUBLIC_LAUNCH=TBD
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Leave that window open.

Open `frontend/index.html` in Chrome.

- Create an account with test data.
- Copy the username from the dashboard.
- Log out and log back in with the **same** names / DOB / identifier.
- Wrong middle name or DOB should fail. That is the encryption trick working.

API check: http://127.0.0.1:8000/docs

---

## 3. Host the API (Render — easiest)

1. Go to https://render.com and sign in with GitHub.
2. Grant access to the **LaCosaNostra** org and the `hireblock` repo.
3. **New → Web Service**.
4. Connect `LaCosaNostra/hireblock`.
5. Settings:
   - Language: Python
   - Root directory: `backend`
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Environment variables:
   - `HIREBLOCK_SECRET` = a long random string (not the default)
   - `HIREBLOCK_PUBLIC_LAUNCH` = `TBD`
7. Create the service. Copy the URL, e.g. `https://hireblock-api.onrender.com`.

Free Render apps sleep. First request after idle can take ~30 seconds.

**Railway** is the same idea: New project → GitHub repo → set start command and env vars.

---

## 4. Point the frontend at the live API

Open `frontend/index.html` and find:

```js
const API = localStorage.getItem("hireblock_api") || "http://127.0.0.1:8000";
```

Change it to your Render URL:

```js
const API = "https://hireblock-api.onrender.com";
```

Commit that change.

Or, in the browser console on the page:

```js
localStorage.setItem("hireblock_api", "https://hireblock-api.onrender.com");
```

then refresh.

---

## 5. Host the frontend page

### Option A — GitHub Pages from the org repo

1. Repo → Settings → Pages.
2. Source: Deploy from a branch.
3. Branch: `main`, folder `/frontend` if offered, otherwise keep `index.html` at repo root.
4. If Pages only serves the root, copy `frontend/index.html` to `index.html` at the repo root and commit.
5. After it builds: `https://lacosanostra.github.io/hireblock/`
   (exact URL depends on org Pages settings).

### Option B — jobs.hireblock.org/demo

1. Open `RyDevApp/degenerate-job-postings`, branch **`docs`**.
2. Upload `frontend/index.html` as `demo/index.html`.
3. Wait for Pages. Visit https://jobs.hireblock.org/demo/

### Option C — Cloudflare Pages / Netlify

Drag the `frontend` folder onto Netlify Drop or Cloudflare Pages. Set the API URL first.

---

## 6. Smoke test on the public URL

1. Open the hosted page.
2. Sign up as Professional with fake data.
3. You should see: early access + launch TBD + a `pro-…` username.
4. Log out. Log in with the same fields. Dashboard opens.
5. Change the middle name. Login must fail.
6. Sign up as Employer using identifier type **FEIN** (`12-3456789`).

If login fails after a good signup, the API URL is wrong or CORS/sleeping server. Hit `/docs` on the API host.

---

## 7. What is still not production

- Matches are preview placeholders.
- Reveal does not show real contact data.
- SQLite on Render is wiped when the instance sleeps/rebuilds unless you add a disk or Postgres.
- No email verify, no admin panel, no real license bureau check.
- SSN collection has legal risk. Keep it demo-only.

When you want persistence on Render: add a Postgres database and set `DATABASE_URL` to the Render Postgres URL.
