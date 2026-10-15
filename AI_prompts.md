# HW5 Prompt Log

Prompts are recorded as used. "Not recorded" means no prompt or title was present in the original file.

## Problem 1: Create the HW5 prompt log

- **Main prompt:**

  ```text
  I'll do HW5 now. Create AI_prompts.md first and keep updating it as we work through the homework.

  There are 11 problems including this one. Put one section for each problem. For each section, save:

  1. problem number and title
  2. the prompt I typed to you
  3. a follow-up prompt if I needed one, and briefly what was missing after the first prompt

  This file should be a log of what I actually ask you to do. Keep the rest of the code and outputs as evidence of the work. Let's do one problem at a time.
  ```
- **Follow-up prompt:** None recorded.

## Problem 2: Campus Customs database inspection

- **Main prompt:**

  ```text
  Problem 2. Let's first understand the Campus Customs database before building anything.

  Open data/campus_customs.db and inspect every table, its fields, and the actual data that matters. Make a working copy called data/campus_customs_new.db. We will change only the working copy later, so keep the original database untouched.

  Also inspect the three open tickets and understand how each ticket connects to the other tables.

  Start output/harness.md. For every database table, list its important fields and give one short explanation of why that table matters for the agents.

  Do not invent anything. Use the actual database.
  ```
- **Follow-up prompt:** None.

## Problem 3: MCP server for the three open tickets

- **Main prompt:**

  ```text
  Problem 3. Now let's build the MCP server.

  Create an MCP server under mcp_server/ using FastMCP. It should use data/campus_customs_new.db, our working database.

  Based on the actual three tickets we studied in Problem 2, create three useful MCP tools that will help unlock those tickets. Choose the tools based on the real database and ticket needs, not generic tools. Give them clear names and make sure they only return information that really exists in the database.

  We do not need to connect or run the MCP server yet.

  In output/harness.md, add each MCP tool, which database table it reads, which ticket it helps with (101, 102, or 103), and one sentence explaining why that tool is useful for that ticket.

  Also create mcp_server/README.md explaining what this MCP server does, which database it uses, and what the three tools do.
  ```
- **Follow-up prompt:** None.

## Problem 4: Connect and smoke-test the MCP server

- **Main prompt:**

  ```text
  Problem 4. Let's connect the MCP server we built to this project so you can actually call its tools.

  Add the local MCP server connection for this project and save the appropriate MCP connection configuration in .mcp.json if that is the format you use.

  Then test each of the three MCP tools one by one through the MCP connection. Do not bypass MCP by querying the database directly for the test.

  Save evidence to output/mcp_smoke.json. For each test, record:
  1) the prompt I asked
  2) the MCP tool name that was called
  3) the output returned by the tool

  Check the results against data/campus_customs_new.db so we know the MCP tools are returning the correct values.

  Show me the three test results when you're done.
  ```
- **Follow-up prompt:** None.

## Problem 5: PydanticAI Campus Customs agent team

- **Main prompt:**

  ```text
  Problem 5. Build the full Campus Customs agent team with PydanticAI.

  Create 5 agents:
  - Boss
  - Inventory
  - Accounting
  - Facilities
  - Customer Service

  Give each agent its own system prompt in backend/prompts/.

  The Boss should read each ticket, decide which specialist agents are needed, delegate the work, and make the final decision.

  The agents should use our MCP server to get or update Campus Customs data. Add more MCP tools if the 3 existing tools are not enough to solve tickets 101, 102, and 103.

  Also make every run append agent actions and tool calls to output/audit_trail.json.

  Update output/harness.md with the agents, their roles, MCP tools, safety rules, human approval rules, and basic cost/loop limits.
  ```
- **Follow-up prompt:** None.

## Problem 6: Pre-run ticket planning

- **Main prompt:**

  ```text
  Problem 6. Help me plan tickets 101, 102, and 103 before we run the agents.

  Create output/desk_tickets.html.

  It should have:
  - one tab for ticket 101
  - one tab for ticket 102
  - one tab for ticket 103
  - a Cash tab
  - a Reflection tab

  For each ticket, write an Expected section only for now. Leave an empty Actual section for later.

  For each Expected section, include:
  - which specialist the Boss should call first and why
  - the agent delegations I expect
  - which MCP tools I expect them to use

  Do not just send every specialist to every ticket. Use only agents that make sense for that ticket.

  Leave the Cash and Reflection tabs mostly empty for later problems.
  ```
- **Follow-up prompt:** None.

## Problem 7: FastAPI dashboard backend

- **Main prompt:**

  ```text
  Problem 7. Build the FastAPI backend in backend/main.py for the React dashboard.

  Add backend routes that can:
  - return tickets 101, 102, and 103 and whether each is open or resolved
  - take a ticket ID and run the agent team on that ticket
  - return recent agent events, including what agents said and which tools they used
  - allow a human to approve a payment or purchase; agents should only prepare it and cash should change only after approval
  - return the current checking balance from cash_accounts
  - reset the working database to its original values

  The backend should run from the backend/ folder with:

  uvicorn main:app --reload --port 8000

  It should be available at http://localhost:8000.

  Also update output/harness.md and list each backend route with its URL and what it does.
  ```
- **Follow-up prompt:** None.

## Problem 8: React Campus Customs dashboard

- **Main prompt:**

  ```text
  Problem 8. Build the frontend dashboard inside frontend/ using React + Vite + TypeScript.

  The dashboard should:
  - list all three tickets
  - let me select one ticket and start the agent team
  - show each agent and what it is saying or doing while the ticket runs
  - show when a ticket becomes resolved
  - show a short summary of what each agent did
  - let a human approve a payment or purchase when required
  - show the checking balance, including changes after an approved payment

  Make the dashboard visually polished and easy to use.

  Tell the front end to talk to my FastAPI backend at http://localhost:8000.

  Make sure the backend allows the Vite frontend origin, usually http://localhost:5173.

  It should run from frontend/ with:

  npm run dev

  Also create output/design.md explaining the dashboard design choices, including layout, how agents look different, how resolved tickets are shown, how cash is shown, and other creative choices. I want a light blue + dark blue tone design. I want simple layout. I want kitsch feeling from that webpage.
  ```
- **Follow-up prompt:** None.

## Problem 9: Run and resolve tickets

- **Main prompt:**

  ```text
  Problem 9.

  Reset data/campus_customs_new.db back to the original data before the full run.

  Write down the starting checking balance.

  Run tickets 101, 102, and 103 in the agent dashboard until all three are solved.

  If any payment or purchase needs human approval, stop and ask me before changing the cash balance.

  Open output/desk_tickets.html from Problem 6.

  For each ticket tab:
  - keep the Expected section
  - fill in the Actual section using the real run
  - include which agents worked
  - what work they gave to other agents
  - which MCP tools they used

  In the Cash tab, write:
  - starting checking balance
  - cash change for each ticket
  - what payment or purchase caused the change
  - dollar amount
  - ending checking balance

  Make sure the ending balance matches cash_accounts in data/campus_customs_new.db.

  Also create:
  - output/resolved_tickets.json
  - output/resolved_board.html

  In output/resolved_tickets.json, include for each ticket:
  - id
  - final status
  - short result
  - what each agent did
  - any human approvals

  In output/resolved_board.html, include screenshots of the React dashboard for solved tickets 101, 102, and 103.

  Add the real run information to output/audit_trail.json.

  Finish output/harness.md so it explains the database tables, MCP tools, five agents, API routes, dashboard, and safety rules.
  ```
- **Follow-up prompt:**

  ```text
  fix it
  ```
- **What was missing after the first prompt:** The configured OpenAI model requires `OPENAI_API_KEY`, but no provider credential is set in the backend environment; without one, real agent runs cannot proceed.

- **Additional follow-up prompt (retrieved from Chat):**

  ```text
  Current provider requirement:
  I need to run this with PORTKEY_API_KEY + only gpt-6-luna through Portkey.

  Use Portkey only, with model ID exactly gpt-6-luna and PORTKEY_API_KEY. Do not fall back to OpenAI, another provider/model, or a mock model for real ticket results. Load the key locally from the root .env; never print, log, commit, or ask me to paste the secret into chat. Verify Portkey’s current endpoint and authentication requirements against its documentation.

  Before any run, inspect the current project files, audit trail, database state, and pending approvals. Preserve existing user changes and append to the audit trail; do not clear it. Reset only data/campus_customs_new.db from the untouched original if needed, then verify the logical database contents and record the starting balance.

  Run tickets one at a time through the dashboard/API. After each run, inspect pending approvals. If a payment or purchase needs approval, stop and ask me before approving or changing cash. Do not mark a ticket resolved from a recommendation alone; use a supported, safe resolution action or report the missing capability. Do not fabricate agent results, approvals, cash changes, or screenshots.

  After successful runs, update the Actual and Cash sections, output/resolved_tickets.json, output/resolved_board.html with real screenshots of genuinely resolved tickets, output/audit_trail.json, and output/harness.md. Confirm the ending balance matches both the dashboard/API and cash_accounts.
  ```

## Problem 10: Review output and reflection

- **Main prompt:**

  ```text
  Problem 10.

  I need to see your output and do my reflection.
  first, open output/desk_tickets.html
  ```
- **Follow-up prompt:**

  ```text
  Problem 10.

  Here's my reflection.
  Put this into Reflection tap

  1. How would you evaluate the performance of the agents on each ticket and why?

  Unfortunately, I could not run it, it was saying "Run Blocked Before Delegation"
  But, I think it will work well as intended. Boss will call correct agents.

  2. For each ticket, how did actual compare to the expected plan you wrote earlier?

  Unfortunately, I could not run it, it was saying "Run Blocked Before Delegation"

  3. What would have been simpler as one agent with tools — and why?

  If the task is simple, we don't need multi-agents. Because multi-agents will consume more tokens and add processes, while not giving effectiveness of the tasks

  4. Describe three new problems Campus Customs might face that this agent team could solve with the tools you built.

  1) stock shortage check
  2) overdue invoice check
  3) bulk-order discount request analysis

  5. Describe three new problems Campus Customs might face that this agent team could not solve with the tools you built, and explain the tools and agents you would need to solve them.

  1) ordering new inventory to suppliers -> We need ordering agents
  2) setting pricing strategy -> we need demand/past sales analysis agent and strategy agent
  3) predicting future demand -> we need demand/past sales analysis agent
  ```
- **What was missing after the first prompt:** The reflection responses had not been provided after the request to open the output.

## Problem 11: Public GitHub submission

- **Main prompt:**

  ```text
  Problem 11.

  Please prepare and submit my HW5 to GitHub following the required file structure in the attached screenshot.

  - Make the GitHub repo PUBLIC.
  - Do not upload my real .env or any API keys.
  - Include the required files shown in the screenshot.
  - Save the public repo URL in output/github_url.txt.
  - Give me the repo URL when finished.

  Do not change my homework content unless needed for submission.
  ```
- **Follow-up prompt:** None.
