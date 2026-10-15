from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
PROMPTS_DIR = PROJECT_ROOT / "backend" / "prompts"
MCP_CONFIG_PATH = PROJECT_ROOT / ".mcp.json"
AUDIT_PATH = PROJECT_ROOT / "output" / "audit_trail.json"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
PORTKEY_MODEL_NAME = "gpt-6-luna"
PORTKEY_API_KEY = os.environ.get("PORTKEY_API_KEY")
_portkey_key_for_client = PORTKEY_API_KEY or "PORTKEY_API_KEY_NOT_CONFIGURED"
_portkey_client = AsyncOpenAI(
    api_key=_portkey_key_for_client,
    base_url=PORTKEY_BASE_URL,
    default_headers={
        "x-portkey-api-key": _portkey_key_for_client,
    },
)
PORTKEY_MODEL = OpenAIChatModel(
    model_name=PORTKEY_MODEL_NAME,
    provider=OpenAIProvider(openai_client=_portkey_client),
)
MAX_MCP_CALLS_PER_TICKET = 14
MAX_SPECIALISTS_PER_TICKET = 3

AgentRole = Literal["Inventory", "Accounting", "Facilities", "Customer Service"]

TICKET_CONTEXT_TOOLS = {
    101: "get_ticket_101_tee_reprint_context",
    102: "get_ticket_102_rent_lease_context",
    103: "get_ticket_103_bulk_hoodie_context",
}
ALLOWED_SPECIALISTS = {
    101: {"Inventory", "Accounting", "Customer Service"},
    102: {"Accounting", "Facilities"},
    103: {"Inventory", "Customer Service"},
}
_AUDIT_LOCK = threading.Lock()


class SpecialistReport(BaseModel):
    specialist: AgentRole
    ticket_id: int
    findings: list[str]
    recommendation: str
    human_approval_required: bool
    approval_reason: str | None


class TicketDecision(BaseModel):
    ticket_id: int
    specialists_consulted: list[AgentRole]
    decision: str
    rationale: list[str]
    human_approval_required: bool
    approval_reason: str | None


class AuditTrail:
    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id

    def append(
        self,
        event_type: str,
        actor: str,
        action: str,
        **details: Any,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event_type": event_type,
            "actor": actor,
            "action": action,
            **details,
        }
        with _AUDIT_LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                records = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(records, list):
                    raise ValueError("Audit trail must contain a JSON array")
            else:
                records = []
            records.append(entry)
            temporary_path = self.path.with_name(
                f".{self.path.name}.{self.run_id}.tmp"
            )
            temporary_path.write_text(
                json.dumps(records, indent=2, ensure_ascii=False, default=str) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(self.path)


@dataclass
class RunDependencies:
    session: ClientSession
    audit: AuditTrail
    ticket_id: int
    mcp_call_count: int = 0
    delegated_specialists: set[str] = field(default_factory=set)

    async def call_mcp(
        self,
        actor: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        if self.mcp_call_count >= MAX_MCP_CALLS_PER_TICKET:
            self.audit.append(
                "limit_reached",
                actor,
                "MCP call limit reached",
                tool_name=tool_name,
                limit=MAX_MCP_CALLS_PER_TICKET,
            )
            raise RuntimeError("MCP call limit reached for this ticket")

        self.mcp_call_count += 1
        self.audit.append(
            "tool_call",
            actor,
            f"Called MCP tool {tool_name}",
            tool_name=tool_name,
            arguments=arguments,
        )
        try:
            result = await self.session.call_tool(tool_name, arguments=arguments)
            if result.isError:
                raise RuntimeError(f"MCP tool {tool_name} returned an error")
            output = result.structuredContent
            if output is None:
                text_blocks = [
                    item.text for item in result.content if hasattr(item, "text")
                ]
                output = text_blocks[0] if len(text_blocks) == 1 else text_blocks
        except Exception as error:
            self.audit.append(
                "tool_call_failed",
                actor,
                f"MCP tool {tool_name} failed",
                tool_name=tool_name,
                error=str(error),
            )
            raise

        self.audit.append(
            "tool_result",
            actor,
            f"Received result from MCP tool {tool_name}",
            tool_name=tool_name,
            output=output,
        )
        return output


def _read_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


boss_agent = Agent(
    model=PORTKEY_MODEL,
    name="boss",
    output_type=TicketDecision,
    instructions=_read_prompt("boss"),
    deps_type=RunDependencies,
    retries=1,
    max_concurrency=1,
    defer_model_check=True,
)
inventory_agent = Agent(
    model=PORTKEY_MODEL,
    name="inventory",
    output_type=SpecialistReport,
    instructions=_read_prompt("inventory"),
    deps_type=RunDependencies,
    retries=1,
    max_concurrency=1,
    defer_model_check=True,
)
accounting_agent = Agent(
    model=PORTKEY_MODEL,
    name="accounting",
    output_type=SpecialistReport,
    instructions=_read_prompt("accounting"),
    deps_type=RunDependencies,
    retries=1,
    max_concurrency=1,
    defer_model_check=True,
)
facilities_agent = Agent(
    model=PORTKEY_MODEL,
    name="facilities",
    output_type=SpecialistReport,
    instructions=_read_prompt("facilities"),
    deps_type=RunDependencies,
    retries=1,
    max_concurrency=1,
    defer_model_check=True,
)
customer_service_agent = Agent(
    model=PORTKEY_MODEL,
    name="customer_service",
    output_type=SpecialistReport,
    instructions=_read_prompt("customer_service"),
    deps_type=RunDependencies,
    retries=1,
    max_concurrency=1,
    defer_model_check=True,
)


def _make_context_tool(
    actor: str,
    mcp_tool_name: str,
    description: str,
):
    async def read_ticket_context(
        ctx: RunContext[RunDependencies],
    ) -> dict[str, Any]:
        return await ctx.deps.call_mcp(actor, mcp_tool_name, {})

    read_ticket_context.__doc__ = description
    return read_ticket_context


def _register_context_tool(
    agent: Agent[RunDependencies, Any],
    actor: str,
    mcp_tool_name: str,
    description: str,
) -> None:
    agent.tool(
        _make_context_tool(actor, mcp_tool_name, description),
        name=mcp_tool_name,
        description=description,
    )


def _make_note_tool(actor: str):
    async def append_internal_ticket_note(
        ctx: RunContext[RunDependencies],
        note: str,
    ) -> dict[str, Any]:
        """Append an internal note to the ticket currently being reviewed."""
        return await ctx.deps.call_mcp(
            actor,
            "append_ticket_note",
            {"ticket_id": ctx.deps.ticket_id, "note": note},
        )

    return append_internal_ticket_note


def _register_note_tool(agent: Agent[RunDependencies, Any], actor: str) -> None:
    agent.tool(
        _make_note_tool(actor),
        name="append_internal_ticket_note",
        description=(
            "Append one concise factual internal note to the current ticket. "
            "This does not authorize external or financial actions."
        ),
    )


def _make_prepare_tool(actor: str):
    async def prepare_financial_action(
        ctx: RunContext[RunDependencies],
        action_type: Literal["payment", "purchase"],
        amount: float,
        description: str,
        reference_type: Literal["invoice", "lease", "ticket"] | None = None,
        reference_id: int | None = None,
    ) -> dict[str, Any]:
        """Prepare an action for human approval without moving cash."""
        return await ctx.deps.call_mcp(
            actor,
            "prepare_financial_action",
            {
                "ticket_id": ctx.deps.ticket_id,
                "action_type": action_type,
                "amount": amount,
                "description": description,
                "reference_type": reference_type,
                "reference_id": reference_id,
            },
        )

    return prepare_financial_action


def _register_prepare_tool(agent: Agent[RunDependencies, Any], actor: str) -> None:
    agent.tool(
        _make_prepare_tool(actor),
        name="prepare_financial_action",
        description=(
            "Prepare a payment or purchase proposal for human review. "
            "This creates a pending proposal and never changes cash or records a payment."
        ),
    )


_register_context_tool(
    inventory_agent,
    "Inventory",
    TICKET_CONTEXT_TOOLS[101],
    "Read the tee order, tee stock, pricing, invoice, and vendor context for ticket 101.",
)
_register_context_tool(
    inventory_agent,
    "Inventory",
    TICKET_CONTEXT_TOOLS[103],
    "Read the bulk hoodie request, matching stock, and pricing for ticket 103.",
)
_register_note_tool(inventory_agent, "Inventory")
_register_prepare_tool(inventory_agent, "Inventory")

_register_context_tool(
    accounting_agent,
    "Accounting",
    TICKET_CONTEXT_TOOLS[101],
    "Read the tee reprint invoice and related vendor and pricing context for ticket 101.",
)
_register_context_tool(
    accounting_agent,
    "Accounting",
    TICKET_CONTEXT_TOOLS[102],
    "Read the rent notice, linked lease, and recorded desk date for ticket 102.",
)
_register_note_tool(accounting_agent, "Accounting")
_register_prepare_tool(accounting_agent, "Accounting")

_register_context_tool(
    facilities_agent,
    "Facilities",
    TICKET_CONTEXT_TOOLS[102],
    "Read the rent notice, linked lease, and recorded desk date for ticket 102.",
)
_register_note_tool(facilities_agent, "Facilities")

_register_context_tool(
    customer_service_agent,
    "Customer Service",
    TICKET_CONTEXT_TOOLS[101],
    "Read the tee order and its current inventory, price, invoice, and vendor records.",
)
_register_context_tool(
    customer_service_agent,
    "Customer Service",
    TICKET_CONTEXT_TOOLS[103],
    "Read the bulk hoodie request and its current inventory and pricing records.",
)
_register_note_tool(customer_service_agent, "Customer Service")


async def _delegate(
    ctx: RunContext[RunDependencies],
    specialist_name: str,
    specialist: Agent[RunDependencies, SpecialistReport],
    task: str,
) -> dict[str, Any]:
    ticket_id = ctx.deps.ticket_id
    if specialist_name not in ALLOWED_SPECIALISTS[ticket_id]:
        raise ValueError(
            f"{specialist_name} is not an allowed specialist for ticket {ticket_id}"
        )
    if specialist_name in ctx.deps.delegated_specialists:
        raise ValueError(f"{specialist_name} has already reviewed this ticket")
    if len(ctx.deps.delegated_specialists) >= MAX_SPECIALISTS_PER_TICKET:
        raise RuntimeError("Specialist delegation limit reached")

    ctx.deps.delegated_specialists.add(specialist_name)
    ctx.deps.audit.append(
        "agent_action",
        "Boss",
        f"Delegated ticket {ticket_id} to {specialist_name}",
        specialist=specialist_name,
        task=task,
    )
    result = await specialist.run(
        task,
        deps=ctx.deps,
        usage_limits=UsageLimits(
            request_limit=3,
            tool_calls_limit=4,
            total_tokens_limit=2500,
        ),
    )
    report = result.output.model_dump(mode="json")
    ctx.deps.audit.append(
        "agent_action",
        specialist_name,
        f"Completed review of ticket {ticket_id}",
        report=report,
    )
    return report


@boss_agent.tool
async def delegate_to_inventory(
    ctx: RunContext[RunDependencies],
    task: str,
) -> dict[str, Any]:
    """Delegate a ticket review to the Inventory specialist."""
    return await _delegate(ctx, "Inventory", inventory_agent, task)


@boss_agent.tool
async def delegate_to_accounting(
    ctx: RunContext[RunDependencies],
    task: str,
) -> dict[str, Any]:
    """Delegate a ticket review to the Accounting specialist."""
    return await _delegate(ctx, "Accounting", accounting_agent, task)


@boss_agent.tool
async def delegate_to_facilities(
    ctx: RunContext[RunDependencies],
    task: str,
) -> dict[str, Any]:
    """Delegate a ticket review to the Facilities specialist."""
    return await _delegate(ctx, "Facilities", facilities_agent, task)


@boss_agent.tool
async def delegate_to_customer_service(
    ctx: RunContext[RunDependencies],
    task: str,
) -> dict[str, Any]:
    """Delegate a ticket review to the Customer Service specialist."""
    return await _delegate(ctx, "Customer Service", customer_service_agent, task)


def _mcp_server_parameters() -> StdioServerParameters:
    configuration = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
    server_config = configuration["mcpServers"]["campus-customs"]
    return StdioServerParameters(
        command=server_config["command"],
        args=server_config["args"],
        cwd=str(PROJECT_ROOT),
    )


def _usage_limits() -> UsageLimits:
    return UsageLimits(
        request_limit=5,
        tool_calls_limit=6,
        total_tokens_limit=6000,
    )


def _model_configuration_error() -> str | None:
    if not PORTKEY_API_KEY:
        return f"PORTKEY_API_KEY is not configured for model {PORTKEY_MODEL_NAME}"
    return None


def _exception_details(error: BaseException) -> str:
    if isinstance(error, BaseExceptionGroup):
        return "; ".join(_exception_details(nested) for nested in error.exceptions)
    return f"{type(error).__name__}: {error}"


async def process_ticket(ticket_id: int) -> TicketDecision:
    if ticket_id not in TICKET_CONTEXT_TOOLS:
        raise ValueError("Ticket ID must be one of 101, 102, or 103")

    run_id = str(uuid4())
    audit = AuditTrail(AUDIT_PATH, run_id)
    audit.append(
        "run_started",
        "Boss",
        f"Started Campus Customs review for ticket {ticket_id}",
        ticket_id=ticket_id,
        model=PORTKEY_MODEL_NAME,
    )

    configuration_error = _model_configuration_error()
    if configuration_error:
        audit.append(
            "run_failed",
            "Boss",
            f"Campus Customs review failed for ticket {ticket_id}",
            ticket_id=ticket_id,
            error=configuration_error,
        )
        raise RuntimeError(configuration_error)

    try:
        async with stdio_client(
            _mcp_server_parameters(), errlog=sys.stderr
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                dependencies = RunDependencies(
                    session=session,
                    audit=audit,
                    ticket_id=ticket_id,
                )
                context = await dependencies.call_mcp(
                    "Boss",
                    TICKET_CONTEXT_TOOLS[ticket_id],
                    {},
                )
                audit.append(
                    "agent_action",
                    "Boss",
                    f"Reviewed MCP context for ticket {ticket_id}",
                    ticket_context=context,
                )
                user_prompt = (
                    f"Review Campus Customs ticket {ticket_id}. Here is the initial "
                    "context returned by the MCP server:\n"
                    f"{json.dumps(context, ensure_ascii=False)}\n"
                    "Decide which specialists are needed, delegate their reviews, "
                    "and return the final recommendation."
                )
                result = await boss_agent.run(
                    user_prompt,
                    deps=dependencies,
                    usage_limits=_usage_limits(),
                )
                decision = result.output
                if decision.ticket_id != ticket_id:
                    raise ValueError("Boss returned a decision for the wrong ticket")
                actual_specialists = dependencies.delegated_specialists
                if not actual_specialists:
                    raise ValueError("Boss must delegate to at least one specialist")
                if set(decision.specialists_consulted) != actual_specialists:
                    raise ValueError(
                        "Boss specialist list does not match completed delegations"
                    )
                audit.append(
                    "agent_action",
                    "Boss",
                    f"Made final recommendation for ticket {ticket_id}",
                    decision=decision.model_dump(mode="json"),
                )
                audit.append(
                    "run_completed",
                    "Boss",
                    f"Completed Campus Customs review for ticket {ticket_id}",
                    ticket_id=ticket_id,
                )
                return decision
    except Exception as error:
        error_details = _exception_details(error)
        audit.append(
            "run_failed",
            "Boss",
            f"Campus Customs review failed for ticket {ticket_id}",
            ticket_id=ticket_id,
            error=error_details,
        )
        raise RuntimeError(error_details) from error


async def process_all_tickets() -> list[TicketDecision]:
    decisions = []
    for ticket_id in TICKET_CONTEXT_TOOLS:
        decisions.append(await process_ticket(ticket_id))
    return decisions


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team")
    parser.add_argument(
        "--ticket-id",
        type=int,
        choices=tuple(TICKET_CONTEXT_TOOLS),
        help="Review one ticket; defaults to all three open tickets",
    )
    arguments = parser.parse_args()
    if arguments.ticket_id is None:
        decisions = await process_all_tickets()
    else:
        decisions = [await process_ticket(arguments.ticket_id)]
    print(
        json.dumps(
            [decision.model_dump(mode="json") for decision in decisions],
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(_main())
