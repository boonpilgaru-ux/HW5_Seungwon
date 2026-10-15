# Campus Customs — HW5

Campus Customs is a ticket-review dashboard backed by a FastAPI service, a React frontend, a five-agent PydanticAI team, and a local MCP server.

## Project layout

- `backend/` contains the FastAPI routes, agent team, data-access and approval logic, request models, and agent prompts.
- `mcp_server/` provides ticket-context tools and controlled note/proposal writes.
- `frontend/` contains the React and Vite dashboard.
- `data/campus_customs.db` is the original database. `data/campus_customs_new.db` is the working database.
- `output/` contains the prompt log, harness notes, run evidence, dashboard HTML, and submission URL.

## Configuration

Create a local `.env` from `.env.example` and set `PORTKEY_API_KEY`. Keep `.env` private; it is excluded by `.gitignore`. All five agents are configured to use only `gpt-6-luna` through Portkey.

## Run locally

Install backend and MCP dependencies from the project root:

```powershell
python -m pip install -r requirements.txt
```

Start the API from `backend/`:

```powershell
python -m uvicorn main:app --reload --port 8000
```

Start the dashboard from `frontend/`:

```powershell
npm install
npm run dev
```

The frontend uses the FastAPI service at `http://localhost:8000`. Agent ticket runs start the MCP server through the project configuration. The working database is used for application operations; the original database is the reset source.

## Safety and evidence

Agents can read ticket context, append internal notes, and prepare payment or purchase proposals. A human must approve a proposal before any payment is recorded or checking cash changes. Actual run status, agent actions, MCP calls, and cash information are documented in `output/`.
