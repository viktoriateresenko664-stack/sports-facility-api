# Desktop Client (`desctop11`)

Desktop app for employee workflows (operator and chief engineer scenarios).

## Stack
- Python 3.11+
- PySide6
- requests

## Entry point
- [main.py](/c:/Users/viktoria/Desktop/API/desctop11/desctop11/desctop/main.py)

## Install and run
1. Create and activate virtual environment.
2. Install dependencies:
   - `pip install PySide6 requests`
3. Start app:
   - `python desctop11/desctop11/desctop/main.py`

## Backend API
- Base URL: `https://sports-facility-api.onrender.com`
- Auth header: `Authorization: Bearer <access_token>`

## Roles
- `OPERATOR`
- `CHIEF_ENGINEER`

## Main API usage
- `POST /auth/employee-login`
- `GET /auth/me`
- `GET /bff/desktop/dashboard`
- `GET /bff/desktop/requests`
- `GET /bff/desktop/requests/all`
- `POST /bff/desktop/requests/{request_id}/assign`
- `GET /bff/desktop/reports`
- `GET /bff/desktop/logs`
- `GET /bff/desktop/employees`

## Error handling expectations
- `401`: session expired, login again
- `403`: no access for current role
- `404`: resource not found
- `409`: business conflict (status transition/report file conflict)
- `422`: validation error
- `500`: server error

## Notes for repository
- Source code is committed.
- Build artifacts are ignored (`dist/`, `build/`, `.exe`).
