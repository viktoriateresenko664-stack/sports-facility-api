# Security Checklist (Burp/curl/PowerShell)

Base URL:
- `https://sports-facility-api.onrender.com`

Use placeholders only:
- `<USER_EMAIL>`
- `<USER_PASSWORD>`
- `<ENGINEER_KEY>`
- `<ENGINEER_PASSWORD>`
- `<ACCESS_TOKEN>`
- `<REFRESH_TOKEN>`
- `<TASK_ID>`
- `<JOB_ID>`
- `<REPORT_PATH>`

## 1. Healthcheck
```powershell
curl.exe -i https://sports-facility-api.onrender.com/health
```
Expected: `200`.

## 2. 401 without token
```powershell
curl.exe -i https://sports-facility-api.onrender.com/auth/me
```
Expected: `401`.

## 3. User login
```powershell
curl.exe -i -X POST https://sports-facility-api.onrender.com/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"<USER_EMAIL>\",\"password\":\"<USER_PASSWORD>\"}"
```
Expected: `200`, returns `access_token`, `refresh_token`.

## 4. Employee login
```powershell
curl.exe -i -X POST https://sports-facility-api.onrender.com/auth/employee-login ^
  -H "Content-Type: application/json" ^
  -d "{\"employee_key\":\"<ENGINEER_KEY>\",\"password\":\"<ENGINEER_PASSWORD>\"}"
```
Expected: `200` for valid credentials, `401` for invalid.

## 5. 403 role denied (USER -> desktop BFF)
```powershell
curl.exe -i https://sports-facility-api.onrender.com/bff/desktop/dashboard ^
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
Expected: `403`.

## 6. Engineer mobile access check
```powershell
curl.exe -i https://sports-facility-api.onrender.com/bff/mobile/tasks ^
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
Expected: `200` for engineer token.

## 7. SQL injection login check
```powershell
curl.exe -i -X POST https://sports-facility-api.onrender.com/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"' OR 1=1 --\",\"password\":\"test\"}"
```
Expected: `401` or `422`, never `200`.

## 8. CORS whitelist check (evil origin)
```powershell
curl.exe -i https://sports-facility-api.onrender.com/health ^
  -H "Origin: https://evil.example"
```
Expected: no permissive wildcard CORS for untrusted origin in production.

## 9. Refresh token rotation/reuse
```powershell
curl.exe -i -X POST https://sports-facility-api.onrender.com/auth/refresh ^
  -H "Content-Type: application/json" ^
  -d "{\"refresh_token\":\"<REFRESH_TOKEN>\"}"
```
Expected: first call issues new token; reusing revoked token should return `401`.

## 10. Logout invalidation
```powershell
curl.exe -i -X POST https://sports-facility-api.onrender.com/auth/logout ^
  -H "Content-Type: application/json" ^
  -d "{\"refresh_token\":\"<REFRESH_TOKEN>\"}"
```
Expected: `204`; old refresh token must not stay valid.

## 11. Rate limit on auth
```powershell
1..12 | ForEach-Object {
  curl.exe -s -o NUL -w "%{http_code}`n" -X POST https://sports-facility-api.onrender.com/auth/login ^
    -H "Content-Type: application/json" ^
    -d "{\"email\":\"<USER_EMAIL>\",\"password\":\"wrong-password\"}"
}
```
Expected: after threshold, responses include `429`.

## 12. Report upload: wrong file key -> 422
```powershell
curl.exe -i -X POST https://sports-facility-api.onrender.com/reports/upload ^
  -H "Authorization: Bearer <ACCESS_TOKEN>" ^
  -F "task_id=<TASK_ID>" ^
  -F "file=@<REPORT_PATH>"
```
Expected: `422` (file key must be `report_file`).

## 13. Report upload: correct key
```powershell
curl.exe -i -X POST https://sports-facility-api.onrender.com/reports/upload ^
  -H "Authorization: Bearer <ACCESS_TOKEN>" ^
  -F "task_id=<TASK_ID>" ^
  -F "report_file=@<REPORT_PATH>" ^
  -F "notes=Report test upload"
```
Expected: `200`.

## 14. Delayed generation job
```powershell
curl.exe -i -X POST https://sports-facility-api.onrender.com/reports/generate-delayed ^
  -H "Authorization: Bearer <ACCESS_TOKEN>" ^
  -H "Content-Type: application/json" ^
  -d "{\"task_id\":<TASK_ID>,\"delay_seconds\":10}"
```
Expected: `200`, returns `job_id` and `status`.

## 15. Job status polling
```powershell
curl.exe -i https://sports-facility-api.onrender.com/reports/jobs/<JOB_ID> ^
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
Expected: `200`, status in `CREATED|ACTIVE|COMPLETED|CANCELLED`.

## 16. XSS payload validation smoke check
```powershell
curl.exe -i -X POST https://sports-facility-api.onrender.com/user-requests ^
  -H "Authorization: Bearer <ACCESS_TOKEN>" ^
  -H "Content-Type: application/json" ^
  -d "{\"facility_id\":1,\"title\":\"<script>alert(1)</script>\",\"description\":\"XSS check request text\"}"
```
Expected: payload is sanitized/escaped and script is not executed in clients.

