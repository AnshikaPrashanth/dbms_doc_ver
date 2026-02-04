# GovVerify - AI-Powered Document Verification

A secure, full-stack system for document verification using OCR, NLP extraction, cryptographic hashing, and an audit trail. Built with Flask, MySQL, MongoDB, and React.

## Screenshots

- `docs/screenshots/home.svg`
- `docs/screenshots/dashboard.svg`
- `docs/screenshots/admin.svg`

Replace the placeholder SVGs with real screenshots for a polished portfolio.

## Features

- OCR + NLP extraction with structured fields
- SHA-256 hashing and verification workflow
- Session auth with admin review flow
- MySQL for core data and MongoDB for audit logs
- Rate-limited authentication to reduce brute force

## Quickstart

### Backend

```bash
cd backend
python -m venv venv
# Windows
.\venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env` from `backend/.env.example` and set real values, especially `SECRET_KEY`.

Run the backend:

```bash
python app.py
```

### Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env` from `frontend/.env.example` and set the API base URL.

Run the frontend:

```bash
npm start
```

## Seed an Admin User

```bash
cd backend
python scripts/seed_admin.py --email admin@example.com --name "Admin User" --password "ChangeMe123!"
```

If the user already exists, you can elevate and reset the password:

```bash
python scripts/seed_admin.py --email admin@example.com --reset-password
```

## Environment Variables

Backend config lives in `backend/.env.example`. Frontend config lives in `frontend/.env.example`.
Frontend and backend run on separate ports, so CORS is enabled with `FRONTEND_ORIGIN`.
