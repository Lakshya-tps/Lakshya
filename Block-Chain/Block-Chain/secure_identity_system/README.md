Secure Identity Platform v2

Overview
This version upgrades the original face-authentication prototype into a more operational system. It keeps the same core idea, but adds stronger capture analysis, structured APIs, richer audit telemetry, and a redesigned dashboard.

What changed
- Pydantic-backed request validation for all JSON capture flows
- Capture quality analysis before register and login requests are accepted
- Expanded SQLite schema with timestamps, quality score, blockchain status, and transaction hash
- Blockchain status reporting for ready, offline, missing, mismatch, and synced states
- Refreshed responsive interface with modern registration, authentication, and operations views

Project Structure
secure_identity_system/
├── backend/
│   ├── app.py
│   ├── blockchain.py
│   ├── database.py
│   ├── face_auth.py
│   ├── schemas.py
│   ├── static/
│   │   ├── script.js
│   │   └── style.css
│   └── templates/
│       ├── base.html
│       ├── admin.html
│       ├── admin_login.html
│       ├── admin_register.html
│       ├── index.html
│       ├── login.html
│       ├── profile.html
│       └── register.html
├── database/
│   └── users.db
├── smart_contract/
│   └── Identity.sol
└── requirements.txt

Requirements
- Python 3.12+ recommended
- Webcam access for browser-based capture
- Ganache optional for blockchain writes and verification

Install
1. Create a virtual environment:
   python -m venv .venv
2. Activate it:
   .venv\Scripts\activate
3. Install dependencies:
   pip install -r requirements.txt

Run
1. Change into the project folder:
   cd secure_identity_system
2. Start the backend:
   python backend/app.py
3. Open:
   http://127.0.0.1:5000

One-command start from the repo root
- Run:
  `.\run_secure_identity.bat`
- This starts the Flask app on `http://127.0.0.1:5055` and opens `http://127.0.0.1:5055/dashboard` automatically.
- In PowerShell, you must use `.\` for files in the current folder.
- If you are one level above the repo root, use:
  `.\Block-Chain\run_secure_identity.bat`

Optional blockchain configuration
- Add `GANACHE_URL` and `CONTRACT_ADDRESS` in `secure_identity_system\.env`
- For hosted RPC providers (Vercel, Alchemy, Infura), also set `BLOCKCHAIN_PRIVATE_KEY`
- Defaults to `http://127.0.0.1:7545` and a zero address until you update them
- Keep the ABI in `backend/blockchain.py` aligned with your deployed contract
 - If you deploy with the bundled Hardhat scripts, `GANACHE_URL` is set to `http://127.0.0.1:8545`

Primary API endpoints
- `GET /api/health`
- `GET /api/overview`
- `POST /api/analyze-capture`
- `POST /api/register`
- `POST /api/login`
- `GET /api/users`
- `GET /api/logs`
- `GET /api/verify/<email>`

Notes
- Face matching still uses OpenCV histogram techniques, not deep-learning embeddings.
- Blockchain is optional: local enrollment still works when the chain is unavailable, but the dashboard will show that state explicitly.
