# Dashboard Design

## Layout

The dashboard uses a compact masthead, a ticket queue on the left, and one focused ticket workspace on the right. The activity feed and approval desk share the workspace so an operator can follow the team and review any proposed money movement without changing screens. On narrow screens, the queue and work areas stack vertically.

## Color and Type

Light blue surfaces and a deep navy frame carry the requested blue palette. Cobalt separates active controls, while small gold and coral accents borrow the bright ink of a campus stationery counter. Bree Serif headlines pair with a clean sans-serif interface face for a little printed-docket character without sacrificing scanning speed.

## Agent Activity

Each of the five roles has a distinct icon and accent color: Boss uses gold, Inventory blue, Accounting slate-blue, Facilities teal, and Customer Service coral. Short status labels and the newest audit event show whether an agent is waiting, using MCP, or has completed a review. The feed polls the backend during a run and preserves the latest recommendation after completion.

## Resolved Tickets

Open tickets stay at the top of the queue. Resolved items move below them, use a green checkmark and a muted row treatment, and cannot be run again from the dashboard. The selected resolved ticket gets a small FILED stamp instead of the run action.

## Cash and Approval

Checking sits in the masthead with its recorded date, making the balance visible without taking over the workspace. Pending payment and purchase proposals appear in a separate review area with the ticket, amount, and description. An approver name is required for either action; the balance refreshes only after the human approval endpoint succeeds.

## Kitsch Details

The CC seal, stamped ticket numbers, tiny star marks, striped top rule, and ticket-office labels reinterpret the earlier Desk Tickets sheet as a slightly nostalgic campus supply counter. These details stay small and functional, leaving the queue, agent reports, and approval controls as the visual focus.

## API

The client uses `VITE_API_BASE_URL`, defaulting to `http://localhost:8000`. The FastAPI backend already allows the Vite origin at `http://localhost:5173`.
