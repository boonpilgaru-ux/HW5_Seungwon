from __future__ import annotations

import json
import sys
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.approvals import (
    InsufficientFunds,
    ProposalConflict,
    ProposalNotFound,
    approve_proposal,
    connect_working_database,
    list_proposals,
    reject_proposal,
    reset_working_database,
)
from backend.agent_team import TICKET_CONTEXT_TOOLS, process_ticket
from backend.models import HumanReview, ResetConfirmation


TICKET_IDS = tuple(TICKET_CONTEXT_TOOLS)
AUDIT_PATH = PROJECT_ROOT / "output" / "audit_trail.json"
app = FastAPI(title="Campus Customs API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/tickets")
def get_tickets() -> list[dict[str, object]]:
    with closing(connect_working_database(read_only=True)) as connection:
        rows = connection.execute(
            """
            SELECT id, type, requester, subject, status
            FROM tickets
            WHERE id IN (?, ?, ?)
            ORDER BY id
            """,
            TICKET_IDS,
        ).fetchall()
    return [
        {
            "ticket_id": row["id"],
            "type": row["type"],
            "requester": row["requester"],
            "subject": row["subject"],
            "status": row["status"],
            "is_open": row["status"] == "open",
            "is_resolved": row["status"] == "resolved",
        }
        for row in rows
    ]


@app.post("/tickets/{ticket_id}/run")
async def run_agent_team(ticket_id: int) -> dict[str, object]:
    if ticket_id not in TICKET_CONTEXT_TOOLS:
        raise HTTPException(status_code=404, detail="Ticket not found")
    with closing(connect_working_database(read_only=True)) as connection:
        ticket = connection.execute(
            "SELECT status FROM tickets WHERE id = ?",
            (ticket_id,),
        ).fetchone()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket["status"] == "resolved":
        raise HTTPException(status_code=409, detail="Ticket is already resolved")

    try:
        decision = await process_ticket(ticket_id)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Agent run failed: {error}",
        ) from error
    return {"ticket_id": ticket_id, "decision": decision.model_dump(mode="json")}


@app.get("/events")
def get_recent_events(
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, list[dict[str, object]]]:
    if not AUDIT_PATH.exists():
        return {"events": []}
    try:
        events = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=500, detail="Audit trail is not valid JSON") from error
    if not isinstance(events, list):
        raise HTTPException(status_code=500, detail="Audit trail must be a JSON array")
    return {"events": list(reversed(events[-limit:]))}


@app.get("/cash")
def get_checking_balance() -> dict[str, object]:
    with closing(connect_working_database(read_only=True)) as connection:
        account = connection.execute(
            "SELECT name, balance, date FROM cash_accounts WHERE name = 'checking'"
        ).fetchone()
    if account is None:
        raise HTTPException(status_code=404, detail="Checking account not found")
    return dict(account)


@app.get("/approvals")
def get_approvals(
    status: Literal["pending", "approved", "rejected"] | None = "pending",
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, list[dict[str, object]]]:
    with closing(connect_working_database()) as connection:
        with connection:
            proposals = list_proposals(connection, status, limit)
    return {"approvals": proposals}


@app.post("/approvals/{proposal_id}/approve")
def approve_financial_action(
    proposal_id: str,
    review: HumanReview,
) -> dict[str, object]:
    try:
        with closing(connect_working_database()) as connection:
            proposal = approve_proposal(connection, proposal_id, review.approved_by)
    except ProposalNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except InsufficientFunds as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProposalConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"approval": proposal}


@app.post("/approvals/{proposal_id}/reject")
def reject_financial_action(
    proposal_id: str,
    review: HumanReview,
) -> dict[str, object]:
    try:
        with closing(connect_working_database()) as connection:
            proposal = reject_proposal(connection, proposal_id, review.approved_by)
    except ProposalNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProposalConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"approval": proposal}


@app.post("/database/reset")
def reset_database(request: ResetConfirmation) -> dict[str, object]:
    if request.confirmation != "RESET":
        raise HTTPException(status_code=400, detail="Explicit RESET confirmation required")
    try:
        reset_working_database()
    except (FileNotFoundError, OSError) as error:
        raise HTTPException(status_code=500, detail="Could not reset working database") from error
    return {
        "reset": True,
        "source": "data/data/campus_customs.db",
        "working_copy": "data/campus_customs_new.db",
    }
