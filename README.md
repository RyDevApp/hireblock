# HIREBLOCK — Early Access Prototype
## Privacy-first anonymous staffing by People Placers Staffing (SecuredStaff™).

__This package is made up of:__
- `frontend/index.html` — early-access signup / login / dashboard
- `backend/` — FastAPI + SQLite that stores **hashes only**, issues JWTs
__Raw PII is never stored on the server. The account key is a SHA-256 of:__
1. First name  
2. Middle name (empty string if none)  
3. Last name  
4. Birth date (`YYYY-MM-DD`)  
5. Identifier type (`dl` | `fein` | `ssn` | `address`)  
6. Identifier value (driver license, FEIN, SSN, or most recent address)
### New signups are marked **early access**. Public launch date is **TBD**.
# Am using test values while you host this. Do not provide your real SSN...
---
## Local test (Windows)
```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set HIREBLOCK_SECRET=change-this-long-random-string
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
### API docs: http://hireblock.org/docs (Under construction)
