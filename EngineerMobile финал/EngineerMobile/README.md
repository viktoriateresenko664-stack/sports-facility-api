# Engineer Mobile (final)

Mobile client for engineers.

## Stack
- Expo / React Native
- Axios + fetch

## API
- Backend: `https://sports-facility-api.onrender.com`
- Engineer auth: `POST /auth/employee-login`

## Install
1. `npm install`
2. `npm start`

## Build APK (EAS)
1. Login to Expo:
   - `npx eas-cli login`
2. Run build:
   - `npx eas-cli build --platform android --profile production`
3. Download APK from the link returned by EAS build output.

## Required endpoints
- `POST /auth/employee-login`
- `GET /auth/me`
- `GET /bff/mobile/tasks`
- `POST /engineer-tasks/{task_id}/start`
- `POST /engineer-tasks/{task_id}/finish`
- `POST /reports/upload`
- `POST /reports/generate-delayed`
- `GET /reports/jobs/{job_id}`

## Report upload contract
- `multipart/form-data`:
  - `task_id`
  - `report_file` (strict key name)
  - `notes` (optional)
- Do not send `engineer_id` from client.

## Realtime behavior
- Polling is supported (`/bff/mobile/tasks`, e.g. every 15s).
- Mobile client must not use desktop sockets (`/ws/tasks`, `/ws/sensors`).

## Repository notes
- Keep only source files in git.
- Ignore artifacts: `node_modules`, `.expo`, `android/build`, `.apk`, `.aab`, credentials/tokens.
