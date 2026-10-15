from contextlib import closing
from pathlib import Path
import sqlite3
import sys
from typing import Any, Literal

from fastmcp import FastMCP


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.approvals import (
    connect_working_database,
    prepare_financial_action as create_financial_action_proposal,
)


DATABASE_PATH = PROJECT_ROOT / "data" / "campus_customs_new.db"
mcp = FastMCP("Campus Customs")


def _connect_read_only() -> sqlite3.Connection:
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Working database not found: {DATABASE_PATH}")

    connection = sqlite3.connect(f"{DATABASE_PATH.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _fetch_one(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[object, ...] = (),
) -> dict[str, Any] | None:
    row = connection.execute(query, parameters).fetchone()
    return dict(row) if row is not None else None


def _require_row(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[object, ...],
    description: str,
) -> dict[str, Any]:
    row = _fetch_one(connection, query, parameters)
    if row is None:
        raise LookupError(f"No {description} found in the working database")
    return row


@mcp.tool
def get_ticket_101_tee_reprint_context() -> dict[str, Any]:
    """Return ticket 101 with its tee stock, pricing, invoice, and vendor rows."""
    with closing(_connect_read_only()) as connection:
        ticket = _require_row(
            connection, "SELECT * FROM tickets WHERE id = ?", (101,), "ticket 101"
        )
        inventory = _require_row(
            connection,
            "SELECT * FROM inventory WHERE sku = ? AND size = ?",
            (ticket["sku"], ticket["size"]),
            "matching inventory row",
        )
        pricing = _require_row(
            connection,
            "SELECT * FROM pricing WHERE sku = ?",
            (ticket["sku"],),
            "matching pricing row",
        )
        invoice = _require_row(
            connection,
            "SELECT * FROM invoices WHERE id = ?",
            (ticket["invoice_id"],),
            "linked invoice",
        )
        vendor = _require_row(
            connection,
            "SELECT * FROM vendors WHERE id = ?",
            (invoice["vendor_id"],),
            "invoice vendor",
        )

    return {
        "ticket": ticket,
        "inventory": inventory,
        "pricing": pricing,
        "invoice": invoice,
        "vendor": vendor,
    }


@mcp.tool
def get_ticket_102_rent_lease_context() -> dict[str, Any]:
    """Return ticket 102 with its linked lease and the recorded desk date."""
    with closing(_connect_read_only()) as connection:
        ticket = _require_row(
            connection, "SELECT * FROM tickets WHERE id = ?", (102,), "ticket 102"
        )
        lease = _require_row(
            connection,
            "SELECT * FROM leases WHERE id = ?",
            (ticket["lease_id"],),
            "linked lease",
        )
        desk = _require_row(
            connection,
            "SELECT * FROM desk LIMIT 1",
            (),
            "desk row",
        )

    return {"ticket": ticket, "lease": lease, "desk": desk}


@mcp.tool
def get_ticket_103_bulk_hoodie_context() -> dict[str, Any]:
    """Return ticket 103 with the matching hoodie inventory and pricing rows."""
    with closing(_connect_read_only()) as connection:
        ticket = _require_row(
            connection, "SELECT * FROM tickets WHERE id = ?", (103,), "ticket 103"
        )
        inventory = _require_row(
            connection,
            "SELECT * FROM inventory WHERE sku = ? AND size = ?",
            (ticket["sku"], ticket["size"]),
            "matching inventory row",
        )
        pricing = _require_row(
            connection,
            "SELECT * FROM pricing WHERE sku = ?",
            (ticket["sku"],),
            "matching pricing row",
        )

    return {"ticket": ticket, "inventory": inventory, "pricing": pricing}


@mcp.tool
def append_ticket_note(ticket_id: int, note: str) -> dict[str, Any]:
    """Append an internal note to an existing ticket and return its updated row."""
    note = note.strip()
    if not note:
        raise ValueError("Ticket note cannot be empty")
    if len(note) > 500:
        raise ValueError("Ticket note cannot exceed 500 characters")

    with closing(connect_working_database()) as connection:
        with connection:
            ticket = _require_row(
                connection,
                "SELECT * FROM tickets WHERE id = ?",
                (ticket_id,),
                f"ticket {ticket_id}",
            )
            existing_notes = ticket["notes"]
            combined_notes = (
                f"{existing_notes}\n{note}" if existing_notes else note
            )
            connection.execute(
                "UPDATE tickets SET notes = ? WHERE id = ?",
                (combined_notes, ticket_id),
            )
            updated_ticket = _require_row(
                connection,
                "SELECT * FROM tickets WHERE id = ?",
                (ticket_id,),
                f"ticket {ticket_id}",
            )

    return updated_ticket


@mcp.tool
def prepare_financial_action(
    ticket_id: int,
    action_type: Literal["payment", "purchase"],
    amount: float,
    description: str,
    reference_type: Literal["invoice", "lease", "ticket"] | None = None,
    reference_id: int | None = None,
) -> dict[str, Any]:
    """Create a pending payment or purchase proposal without changing cash."""
    with closing(connect_working_database()) as connection:
        with connection:
            proposal = create_financial_action_proposal(
                connection,
                ticket_id,
                action_type,
                amount,
                description,
                reference_type,
                reference_id,
            )
    return proposal


if __name__ == "__main__":
    mcp.run()
