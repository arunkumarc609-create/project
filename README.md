# CivicPulse — Smart Civic Issue Priority and Resolution System

A full-stack student-project starter using Flask, SQLite (upgradeable to PostgreSQL), a trained scikit-learn text classifier, Leaflet/OpenStreetMap, browser GPS, photo uploads, complaint tracking, and a role-protected authority dashboard.

## Important limitations

- `ml/civic_issues.csv` is a small illustrative dataset created for this starter. The included baseline model is real trained ML, but its predictions are not validated for operational municipal use. Replace it with a larger, reviewed, representative, labelled dataset and evaluate it before making claims about accuracy.
- The priority score is a transparent weighted formula, not a trained ML model.
- Local photo storage is for development only. Use private object storage, file scanning, retention rules, and signed access in production.
- This project is a development baseline, not a security-audited production service.

## Requirements

- Python 3.10+ (3.11 recommended)
- Internet access for Leaflet map tiles and OpenStreetMap geocoding

## Windows 11 setup (PowerShell)

1. Extract the ZIP to a folder such as `C:\CivicPulse`.
2. Open PowerShell in that folder.
3. Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

4. Train the model:

```powershell
python train_model.py
```

5. Run the website:

```powershell
python app.py
```

6. Open `http://127.0.0.1:5000` in your browser. The SQLite database `civicpulse.db` is created automatically.

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again.

## Development accounts

A first-run authority account is created automatically:

- Email: `admin@civicpulse.local`
- Password: `ChangeMe123!`

Change these before running outside local development. You can configure the first-run account with environment variables before starting the app:

```powershell
$env:CIVICPULSE_ADMIN_EMAIL="your-admin@example.com"
$env:CIVICPULSE_ADMIN_PASSWORD="use-a-long-unique-password"
$env:SECRET_KEY="a-long-random-secret"
python app.py
```

Set `CIVICPULSE_ADMIN_EMAIL` and `CIVICPULSE_ADMIN_PASSWORD` before the first run to choose your initial authority account. Existing accounts are not overwritten if the email already exists.

## Database

SQLite is the default and is suitable for local development and demonstration. For deployment, configure PostgreSQL and set `DATABASE_URL` to the provider's connection string. Verify the provider's SSL requirements and use migrations for schema changes before production.

## Map and location

- Tap the map to place a pin.
- Use **Use my GPS** to request browser geolocation permission. GPS requires localhost or HTTPS and user permission.
- Search an address or six-digit PIN code.
- The map uses OpenStreetMap tiles. Public Nominatim geocoding has a usage policy and is not intended for heavy production traffic; use an appropriate provider for a public deployment.

## ML model

`train_model.py` trains a TF-IDF + Logistic Regression text classifier from `ml/civic_issues.csv`, prints a holdout evaluation report, and saves `ml/civic_model.joblib`. Add balanced examples for each class, including local phrasing and misspellings, and evaluate on a genuinely separate test set. Do not use the small starter dataset's score as a real-world performance claim.

## Features included

- Citizen registration and login with password hashing
- ML category prediction endpoint (`POST /api/predict`)
- Complaint submission with coordinates, severity, safety risk, optional photo
- Persistent complaint records in SQLite
- Weighted priority score and priority tier
- Citizen complaint list and status history
- Authority role checks for status changes
- Authority dashboard and map markers
- Photo access limited to the reporter and authority

## Before public deployment

Use HTTPS; replace the development secret; change the default authority credentials; use PostgreSQL and migrations; add CSRF protection, rate limiting, email verification/password reset, backups, logging, monitoring, secure private object storage, retention/privacy notices, and security testing. Review the local laws and organizational process before collecting location or image data from the public.
