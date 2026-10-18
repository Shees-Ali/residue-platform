# web

React 18 + TypeScript + Vite + Tailwind + React Router + Vitest. Firebase Auth/Firestore, Leaflet maps.

```
cp .env.example .env
npm install
npm run dev        # http://localhost:5173, /health for the health page
npm test
npm run gen:api    # typed client from openapi.json
```

Routes: `/farmer`, `/transporter`, `/factory`, `/market`, `/admin`, `/call`, `/health` (`/` redirects to `/market`). Hosting config is the root `../firebase.json` (Firestore rules and emulators: `../deploy/firebase.json`).
