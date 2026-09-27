# Support Console Frontend (React + Vite)

The web UI of the **AI Customer Support Assistant** project. It drives the
whole pipeline in the browser:

| Screen / component | What it shows | Task |
| ------------------ | ------------- | ---- |
| `SessionAutoStart.jsx` | one-click start of a simulated conversation | 3 |
| `SessionConfiguration.jsx` / `CustomerConfigurationCard` | persona, scenario, issue severity, patience, expected resolution | 3 |
| `SupportConsole.jsx` (conversation) | turn-by-turn simulated customer messages and agent replies | 3 |
| `SupportConsole.jsx` (AI Analysis) | intent, customer emotion, frustration score, sentiment, satisfaction trend, confidence | 4 |
| `SupportConsole.jsx` (Knowledge Used) | retrieved support articles / policies with source + page | 5 |
| `SupportConsole.jsx` (Suggested Response) | context-aware reply suggestion + "Check my draft" quality bars (tone / clarity / empathy / professionalism) + coaching tips | 6 |
| `SupportConsole.jsx` (Escalation Risk Monitor) | risk badge, score bar (0–100), trend, indicator chips, "why this score" reasoning, alert-threshold configurator and escalation alert banner | 6 |
| `Analytics.jsx` / `SessionResult.jsx` | session summary, transcript and per-turn analysis | 3–6 |

## Run it

```bash
cd support_console_frontend
npm install
npm run dev          # http://localhost:5173  (needs the backend on port 8000)
```

## Build it

```bash
npm run build        # writes dist/ - served by the backend at http://127.0.0.1:8000/
```

The build output is **committed on purpose**, so the FastAPI backend
(`../task3_customer_simulator_agent/api.py`) can serve the working Support
Console without a build step.

## Backend base URL

`src/services/api.js` points at `http://127.0.0.1:8000` (customer
simulator + support-assistance router on the same port). Change it there
if you run the backend elsewhere.

## Tech

React 19 · React Router 7 · Vite 8 · Axios. Default Vite template notes:
see the original scaffolding below.


Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
