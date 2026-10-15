# Campus Customs Database Harness

## Source and Working Copy

The original database is `data/campus_customs.db`. The working copy is `data/campus_customs_new.db`. The working copy was copied from the original and verified byte-for-byte; make subsequent database changes only to the working copy.

The database has 9 tables. The source passed SQLite `integrity_check` (`ok`) and `foreign_key_check` (no violations). Declared foreign keys are listed after the table guide.

## Tables

| Table | Important fields and current data | Why it matters for agents |
|---|---|---|
| `cash_accounts` (1 row) | `name` (primary key), `balance`, `date`; checking balance is $3,400 as of 2026-08-31. | Shows recorded funds and the date that balance applies to when assessing financial context. |
| `desk` (1 row) | `date_today`, `notes`; date is 2026-08-31 and notes are NULL. | Anchors due-date and recency reasoning to the database's current date. |
| `inventory` (10 rows) | Composite primary key `sku` + `size`; also `name`, `qty`, `location`. Tee size S and crest mug OS have 0; hoodie M has 8 in Aisle A. | Establishes on-hand quantities, variants, and where stock is located. |
| `invoices` (1 row) | `id` (primary key), `vendor_id`, `amount`, `due_date`, `status`, `description`; invoice 501 is open for $840, due 2026-08-28, description `Rush reprint CC-TEE-WHITE S`. | Supplies payable amount, timing, status, and the vendor reference for purchase decisions. |
| `leases` (1 row) | `id` (primary key), `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`; lease 1 is the Chapel Street shop, landlord Elm City Properties, rent $2,400, next due 2026-09-02. | Provides rent obligation details and supports matching rent notices to a lease. |
| `payments` (0 rows) | `id` (primary key), `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`; currently empty. | Is the record of payments and their references, funding account, date, and approver; no payment is recorded yet. |
| `pricing` (4 rows) | `sku` (primary key), `unit_cost`, `list_price`; hoodie $22/$58, tee $8/$28, cap $6/$22, mug $3.50/$14 (cost/list). | Provides cost and list-price context for order and discount decisions. |
| `tickets` (3 rows) | `id` (primary key), `type`, `requester`, `subject`, optional `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`; tickets 101-103 are all open. | Holds incoming work, its requested action and details, workflow status, and links to related records. |
| `vendors` (3 rows) | `id` (primary key), `name`, `specialty`, `lead_days`; Bulldog Print Co (apparel reprint, 5 days), Elm City Gifts (mugs and small goods, 3 days), QuickShip CT (local courier, 1 day). | Identifies supplier capabilities and stated lead times for sourcing and fulfillment context. |

## Open Tickets and Related Records

- **101, customer order:** Tauhid Zaman requests one `CC-TEE-WHITE`, size S. Inventory reports 0 at Aisle B; pricing is $8 cost and $28 list. Ticket `invoice_id=501` references the open $840 invoice due 2026-08-28. Invoice 501 has `vendor_id=1`, which resolves to Bulldog Print Co (apparel reprint, 5 lead days). The database date is 2026-08-31. The invoice description is `Rush reprint CC-TEE-WHITE S`.
- **102, rent notice:** Elm City Properties' open notice says shop rent is due in 2 days. Ticket `lease_id=1` references the Chapel Street shop lease with Elm City Properties, monthly rent $2,400, and `next_due=2026-09-02`, two days after the database date 2026-08-31. This ticket has no invoice reference.
- **103, price override:** Yale AI Club asks for a bulk discount on 20 `CC-HOOD-NAVY` hoodies, size M. Inventory reports 8 in Aisle A; pricing is $22 cost and $58 list. This ticket has no invoice or lease reference.

## Relationships

Declared foreign keys:

- `tickets.invoice_id` -> `invoices.id`
- `tickets.lease_id` -> `leases.id`
- `invoices.vendor_id` -> `vendors.id`

Additional useful joins are represented by matching values, not declared foreign keys: `tickets.sku` to `inventory.sku` and `pricing.sku`; ticket SKU plus size to the inventory variant; and invoice `vendor_id` to `vendors.id` (the last is declared above). `payments.kind` and `payments.ref_id` form a generic-looking reference pair in the schema, but there are no payment rows and no declared foreign key for that pair.

## Problem 3 MCP Tools

The FastMCP server in `mcp_server/server.py` reads `data/campus_customs_new.db`; its only write tool appends internal notes to existing tickets.

| MCP tool | Tables read | Ticket | Why it is useful |
|---|---|---:|---|
| `get_ticket_101_tee_reprint_context` | `tickets`, `inventory`, `pricing`, `invoices`, `vendors` | 101 | Shows the requested tee's actual stock and price alongside the linked reprint invoice and its vendor details. |
| `get_ticket_102_rent_lease_context` | `tickets`, `leases`, `desk` | 102 | Pairs the rent notice with the matching lease terms and the database's recorded date. |
| `get_ticket_103_bulk_hoodie_context` | `tickets`, `inventory`, `pricing` | 103 | Shows the bulk order request next to available hoodie quantity and the stored unit cost and list price. |
| `append_ticket_note` | `tickets` (writes `notes`) | 101, 102, 103 | Records an internal, reviewable recommendation on an existing ticket without committing a financial or fulfillment action. |
| `prepare_financial_action` | `pending_approvals` (writes a pending proposal) | 101, 102, 103 | Prepares a payment or purchase for human review without inserting a payment or changing cash. |

## Problem 5 PydanticAI Agent Team

The team implementation is `backend/agent_team.py`; each agent loads its own system prompt from `backend/prompts/`. Agents call the FastMCP tools over the configured stdio MCP connection. They do not access SQLite directly.

Run from the workspace root with `python -m backend.agent_team`; add `--ticket-id 101`, `102`, or `103` to process one ticket. On startup, the backend reads the root `.env` file; configure `PORTKEY_API_KEY` there or in the process environment. All five agents use only `gpt-6-luna` through Portkey's OpenAI-compatible endpoint at `https://api.portkey.ai/v1`; no model override or direct OpenAI fallback is used.

| Agent | Role | MCP tools available |
|---|---|---|
| Boss | Reads the ticket context, selects relevant specialists, delegates, and makes the final recommendation. | Ticket 101, 102, and 103 context tools; delegation tools for the specialists. |
| Inventory | Checks product variants, quantities, locations, costs, and list prices for tickets 101 and 103; may prepare a purchase proposal. | `get_ticket_101_tee_reprint_context`, `get_ticket_103_bulk_hoodie_context`, `append_ticket_note`, `prepare_financial_action` |
| Accounting | Reviews the reprint invoice and rent obligation; may prepare a payment proposal but cannot approve it. | `get_ticket_101_tee_reprint_context`, `get_ticket_102_rent_lease_context`, `append_ticket_note`, `prepare_financial_action` |
| Facilities | Matches the rent notice to the recorded lease and desk date. | `get_ticket_102_rent_lease_context`, `append_ticket_note` |
| Customer Service | Prepares evidence-based internal response recommendations for the customer/order and bulk-discount tickets. | `get_ticket_101_tee_reprint_context`, `get_ticket_103_bulk_hoodie_context`, `append_ticket_note` |

### Safety and Approval

- MCP reads are grounded in rows returned by the working database. Agents must label missing information as unknown and must not invent stock, terms, prices, or approvals.
- Agents may append an internal ticket note or create a `pending_approvals` proposal through MCP. A proposal does not create a payment or alter cash. Agents cannot approve proposals or write directly to SQLite.
- Only the human approval API can insert a payment and debit checking. Human approval is required before paying an invoice or rent, placing or promising a reorder/fulfillment, changing prices or granting a discount, contacting a requester/landlord/vendor, or closing a ticket. The MCP server has no approval tool.
- `output/audit_trail.json` is an append-only JSON array of run starts/results, specialist delegation actions, and MCP tool calls/results, including failures.

### Cost and Loop Limits

- Boss: at most 5 model requests, 6 tool calls, and 6,000 tokens per ticket.
- Each specialist: at most 3 model requests, 4 tool calls, and 2,500 tokens per ticket; at most 3 distinct specialists are delegated per ticket.
- All agents share a cap of 14 MCP calls per ticket. Each agent retries at most once. All five agents use `gpt-6-luna` through Portkey; the backend does not read `OPENAI_API_KEY` or allow a model override.

## Problem 7 FastAPI Backend

Run from `backend/` with `uvicorn main:app --reload --port 8000`. The local API base URL is `http://localhost:8000`.

| Method and URL | Purpose |
|---|---|
| `GET http://localhost:8000/tickets` | Returns tickets 101, 102, and 103 with their recorded status and open/resolved flags. |
| `POST http://localhost:8000/tickets/{ticket_id}/run` | Runs the agent team for one supported ticket and returns the final decision. |
| `GET http://localhost:8000/events?limit=50` | Returns recent audit events, including agent actions, statements, and MCP tool calls/results. |
| `GET http://localhost:8000/approvals?status=pending&limit=100` | Lists pending proposals for human review. |
| `POST http://localhost:8000/approvals/{proposal_id}/approve` | Requires `{"approved_by":"..."}`; atomically records the payment and reduces checking only after approval. |
| `POST http://localhost:8000/approvals/{proposal_id}/reject` | Requires `{"approved_by":"..."}`; rejects a pending proposal without changing cash. |
| `GET http://localhost:8000/cash` | Returns the current checking balance and its recorded date. |
| `POST http://localhost:8000/database/reset` | Requires `{"confirmation":"RESET"}`; restores the working DB from the untouched original database. |

FastAPI allows browser requests from local React development servers on ports 3000 and 5173.
