from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKING_DATABASE = PROJECT_ROOT / "data" / "campus_customs_new.db"
ORIGINAL_DATABASE = PROJECT_ROOT / "data" / "campus_customs.db"


class ProposalNotFound(LookupError):
    pass


class ProposalConflict(ValueError):
    pass


class InsufficientFunds(ValueError):
    pass


def connect_working_database(read_only: bool = False) -> sqlite3.Connection:
    if not WORKING_DATABASE.is_file():
        raise FileNotFoundError(f"Working database not found: {WORKING_DATABASE}")
    mode = "ro" if read_only else "rw"
    uri = f"{WORKING_DATABASE.as_uri()}?mode={mode}"
    connection = sqlite3.connect(uri, uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_approval_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_approvals (
            id TEXT PRIMARY KEY,
            ticket_id INTEGER NOT NULL REFERENCES tickets(id),
            action_type TEXT NOT NULL CHECK (action_type IN ('payment', 'purchase')),
            amount REAL NOT NULL CHECK (amount > 0),
            description TEXT NOT NULL,
            reference_type TEXT CHECK (
                reference_type IS NULL OR reference_type IN ('invoice', 'lease', 'ticket')
            ),
            reference_id INTEGER,
            account TEXT NOT NULL DEFAULT 'checking',
            status TEXT NOT NULL DEFAULT 'pending' CHECK (
                status IN ('pending', 'approved', 'rejected')
            ),
            created_at TEXT NOT NULL,
            approved_by TEXT,
            approved_at TEXT,
            rejected_by TEXT,
            rejected_at TEXT,
            payment_id INTEGER
        )
        """
    )


def _approval_table_exists(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'pending_approvals'"
        ).fetchone()
        is not None
    )


def _fetch_proposal(
    connection: sqlite3.Connection,
    proposal_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM pending_approvals WHERE id = ?",
        (proposal_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def prepare_financial_action(
    connection: sqlite3.Connection,
    ticket_id: int,
    action_type: str,
    amount: float,
    description: str,
    reference_type: str | None = None,
    reference_id: int | None = None,
) -> dict[str, Any]:
    if action_type not in {"payment", "purchase"}:
        raise ValueError("Action type must be payment or purchase")
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("Amount must be a finite positive number")

    description = description.strip()
    if not description or len(description) > 500:
        raise ValueError("Description must contain 1 to 500 characters")

    if action_type == "purchase":
        if reference_type is None and reference_id is None:
            reference_type, reference_id = "ticket", ticket_id
        if reference_type != "ticket" or reference_id != ticket_id:
            raise ValueError("Purchase proposals must reference their ticket")
    elif reference_type not in {"invoice", "lease"} or reference_id is None:
        raise ValueError("Payment proposals must reference an invoice or lease")

    ticket = connection.execute(
        "SELECT id, status FROM tickets WHERE id = ?",
        (ticket_id,),
    ).fetchone()
    if ticket is None:
        raise ProposalNotFound(f"Ticket {ticket_id} was not found")
    if ticket["status"] == "resolved":
        raise ProposalConflict("Cannot prepare an action for a resolved ticket")

    target_table = {"invoice": "invoices", "lease": "leases", "ticket": "tickets"}.get(
        reference_type
    )
    if target_table is not None:
        target = connection.execute(
            f'SELECT id FROM "{target_table}" WHERE id = ?',
            (reference_id,),
        ).fetchone()
        if target is None:
            raise ProposalNotFound(f"Referenced {reference_type} {reference_id} was not found")

    cash_account = connection.execute(
        "SELECT name FROM cash_accounts WHERE name = 'checking'"
    ).fetchone()
    if cash_account is None:
        raise ProposalConflict("Checking account is not present in the working database")

    ensure_approval_table(connection)
    proposal_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO pending_approvals (
            id, ticket_id, action_type, amount, description,
            reference_type, reference_id, account, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'checking', 'pending', ?)
        """,
        (
            proposal_id,
            ticket_id,
            action_type,
            amount,
            description,
            reference_type,
            reference_id,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    proposal = _fetch_proposal(connection, proposal_id)
    if proposal is None:
        raise RuntimeError("Prepared approval proposal could not be retrieved")
    return proposal


def list_proposals(
    connection: sqlite3.Connection,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if not _approval_table_exists(connection):
        return []
    if status is not None:
        rows = connection.execute(
            "SELECT * FROM pending_approvals WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT * FROM pending_approvals ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def approve_proposal(
    connection: sqlite3.Connection,
    proposal_id: str,
    approved_by: str,
) -> dict[str, Any]:
    approved_by = approved_by.strip()
    if not approved_by or len(approved_by) > 100:
        raise ValueError("Approver name must contain 1 to 100 characters")
    if not _approval_table_exists(connection):
        raise ProposalNotFound(f"Approval proposal {proposal_id} was not found")

    connection.execute("BEGIN IMMEDIATE")
    try:
        proposal = _fetch_proposal(connection, proposal_id)
        if proposal is None:
            raise ProposalNotFound(f"Approval proposal {proposal_id} was not found")
        if proposal["status"] != "pending":
            raise ProposalConflict("Approval proposal is no longer pending")

        cash = connection.execute(
            "SELECT balance FROM cash_accounts WHERE name = ?",
            (proposal["account"],),
        ).fetchone()
        if cash is None:
            raise ProposalConflict("Approval account was not found")
        balance = float(cash["balance"])
        amount = float(proposal["amount"])
        if amount > balance:
            raise InsufficientFunds("Checking balance is insufficient for this action")

        action_type = proposal["action_type"]
        reference_type = proposal["reference_type"]
        reference_id = proposal["reference_id"]
        payment_kind = action_type
        if action_type == "payment" and reference_type == "invoice":
            invoice = connection.execute(
                "SELECT amount, status FROM invoices WHERE id = ?",
                (reference_id,),
            ).fetchone()
            if invoice is None or invoice["status"] != "open":
                raise ProposalConflict("Referenced invoice is no longer open")
            paid = connection.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments "
                "WHERE kind = 'invoice_payment' AND ref_id = ?",
                (reference_id,),
            ).fetchone()[0]
            remaining = float(invoice["amount"]) - float(paid)
            if amount > remaining:
                raise ProposalConflict("Payment exceeds the remaining invoice balance")
            payment_kind = "invoice_payment"
        elif action_type == "payment" and reference_type == "lease":
            lease = connection.execute(
                "SELECT monthly_rent FROM leases WHERE id = ?",
                (reference_id,),
            ).fetchone()
            if lease is None:
                raise ProposalNotFound(f"Referenced lease {reference_id} was not found")
            if amount > float(lease["monthly_rent"]):
                raise ProposalConflict("Rent payment exceeds the recorded monthly rent")
            payment_kind = "rent_payment"
        elif action_type == "purchase":
            reference_id = proposal["ticket_id"]

        paid_at = datetime.now(timezone.utc).isoformat()
        cursor = connection.execute(
            """
            INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payment_kind,
                reference_id,
                amount,
                proposal["account"],
                paid_at,
                approved_by,
            ),
        )
        new_balance = balance - amount
        connection.execute(
            "UPDATE cash_accounts SET balance = ? WHERE name = ?",
            (new_balance, proposal["account"]),
        )
        if action_type == "payment" and reference_type == "invoice":
            if math.isclose(amount, remaining, rel_tol=1e-9, abs_tol=1e-9):
                connection.execute(
                    "UPDATE invoices SET status = 'paid' WHERE id = ?",
                    (reference_id,),
                )

        connection.execute(
            """
            UPDATE pending_approvals
            SET status = 'approved', approved_by = ?, approved_at = ?, payment_id = ?
            WHERE id = ? AND status = 'pending'
            """,
            (approved_by, paid_at, cursor.lastrowid, proposal_id),
        )
        updated_proposal = _fetch_proposal(connection, proposal_id)
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    if updated_proposal is None:
        raise RuntimeError("Approved proposal could not be retrieved")
    updated_proposal["new_balance"] = new_balance
    return updated_proposal


def reject_proposal(
    connection: sqlite3.Connection,
    proposal_id: str,
    rejected_by: str,
) -> dict[str, Any]:
    rejected_by = rejected_by.strip()
    if not rejected_by or len(rejected_by) > 100:
        raise ValueError("Reviewer name must contain 1 to 100 characters")
    if not _approval_table_exists(connection):
        raise ProposalNotFound(f"Approval proposal {proposal_id} was not found")

    connection.execute("BEGIN IMMEDIATE")
    try:
        proposal = _fetch_proposal(connection, proposal_id)
        if proposal is None:
            raise ProposalNotFound(f"Approval proposal {proposal_id} was not found")
        if proposal["status"] != "pending":
            raise ProposalConflict("Approval proposal is no longer pending")
        rejected_at = datetime.now(timezone.utc).isoformat()
        connection.execute(
            """
            UPDATE pending_approvals
            SET status = 'rejected', rejected_by = ?, rejected_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (rejected_by, rejected_at, proposal_id),
        )
        updated_proposal = _fetch_proposal(connection, proposal_id)
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    if updated_proposal is None:
        raise RuntimeError("Rejected proposal could not be retrieved")
    return updated_proposal


def reset_working_database() -> None:
    if not ORIGINAL_DATABASE.is_file():
        raise FileNotFoundError(f"Original database not found: {ORIGINAL_DATABASE}")
    source_uri = f"{ORIGINAL_DATABASE.as_uri()}?mode=ro"
    source = sqlite3.connect(source_uri, uri=True, timeout=10)
    destination = sqlite3.connect(WORKING_DATABASE, timeout=10)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
