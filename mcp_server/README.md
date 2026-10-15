# Campus Customs MCP Server

This FastMCP server provides database context, internal ticket notes, and pending financial-action proposals for the three Campus Customs tickets. It uses the working database at `data/campus_customs_new.db`.

## Tools

- `get_ticket_101_tee_reprint_context` returns ticket 101 and its related inventory, pricing, invoice, and vendor rows.
- `get_ticket_102_rent_lease_context` returns ticket 102, its linked lease, and the desk date.
- `get_ticket_103_bulk_hoodie_context` returns ticket 103 and the matching hoodie inventory and pricing rows.
- `append_ticket_note` appends a non-empty internal note of at most 500 characters to an existing ticket and returns the updated ticket row. This is the only write tool; it cannot change financial, inventory, pricing, lease, or ticket-status records.
- `prepare_financial_action` creates a pending payment or purchase proposal linked to a ticket and, when needed, an invoice or lease. It does not insert into `payments` or change cash.

Read tools return database row fields as stored. Agents can append notes and prepare proposals, but cannot approve them or change cash. Only the FastAPI human-approval route can record a payment and debit the checking account. Agent runs access these tools over MCP and log tool calls and agent actions in `output/audit_trail.json`.

## Dependency

Install the dependencies with `python -m pip install -r mcp_server/requirements.txt`.

To launch the server later, run `python mcp_server/server.py` from the workspace root.
