# web

React 18 + TypeScript + Vite + Tailwind + React Router + Vitest. Firebase Auth/Firestore, Leaflet maps.

```
cp .env.example .env
npm install
npm run dev        # http://localhost:5173, /health for the health page
npm test
npm run gen:api    # typed client from openapi.json
```

Routes: `/admin`, `/transporter`, `/factory`, `/market`, `/call`, `/health`. Hosting config is in `../deploy/firebase.json`.
