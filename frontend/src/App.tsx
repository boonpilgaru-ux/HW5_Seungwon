import { useEffect, useState } from "react";
import {
  Activity,
  BadgeCheck,
  Building2,
  CheckCircle2,
  CircleAlert,
  Clock3,
  FileText,
  LoaderCircle,
  MessageCircle,
  PackageSearch,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Wallet,
  X,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const POLL_INTERVAL = 850;

interface Ticket {
  ticket_id: number;
  type: string;
  requester: string;
  subject: string;
  status: string;
  is_open: boolean;
  is_resolved: boolean;
}

interface CashAccount {
  name: string;
  balance: number;
  date: string;
}

interface Approval {
  id: string;
  ticket_id: number;
  action_type: "payment" | "purchase";
  amount: number;
  description: string;
  reference_type: string | null;
  reference_id: number | null;
  status: "pending" | "approved" | "rejected";
  created_at: string;
}

interface SpecialistReport {
  specialist?: string;
  findings?: string[];
  recommendation?: string;
  human_approval_required?: boolean;
  approval_reason?: string | null;
}

interface TicketDecision {
  ticket_id: number;
  specialists_consulted: string[];
  decision: string;
  rationale: string[];
  human_approval_required: boolean;
  approval_reason: string | null;
}

interface AgentEvent {
  timestamp?: string;
  run_id?: string;
  ticket_id?: number;
  event_type?: string;
  actor?: string;
  action?: string;
  tool_name?: string;
  report?: SpecialistReport;
  decision?: TicketDecision;
  output?: unknown;
}

interface EventResponse {
  events: AgentEvent[];
}

const AGENTS = [
  { name: "Boss", role: "Desk lead", Icon: Sparkles, tone: "boss" },
  { name: "Inventory", role: "Stockroom", Icon: PackageSearch, tone: "inventory" },
  { name: "Accounting", role: "Ledger", Icon: FileText, tone: "accounting" },
  { name: "Facilities", role: "Property", Icon: Building2, tone: "facilities" },
  { name: "Customer Service", role: "Guest desk", Icon: MessageCircle, tone: "service" },
] as const;

const TICKET_TYPE: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price override",
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String(payload.detail)
        : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return payload as T;
}

async function fetchEvents(): Promise<AgentEvent[]> {
  const result = await request<EventResponse>("/events?limit=100");
  return result.events;
}

function latestRunIds(events: AgentEvent[]): Record<number, string> {
  const ids: Record<number, string> = {};
  for (const event of events) {
    if (
      event.event_type === "run_started" &&
      typeof event.ticket_id === "number" &&
      event.run_id &&
      !ids[event.ticket_id]
    ) {
      ids[event.ticket_id] = event.run_id;
    }
  }
  return ids;
}

function eventSummary(event: AgentEvent | undefined): string {
  if (!event) return "Waiting for assignment";
  if (event.report) {
    const finding = event.report.findings?.[0];
    return [event.report.recommendation, finding].filter(Boolean).join(" ") || "Review complete";
  }
  if (event.decision) return event.decision.decision;
  if (event.tool_name) {
    if (event.event_type === "tool_call") return `Calling ${event.tool_name}`;
    if (event.event_type === "tool_result") return `Returned from ${event.tool_name}`;
    return event.tool_name;
  }
  return event.action || event.event_type || "Reviewing ticket";
}

function agentStatus(
  agentName: string,
  event: AgentEvent | undefined,
  isRunning: boolean,
  decision: TicketDecision | undefined,
): string {
  if (agentName === "Boss" && decision) return "Decision ready";
  if (!event) return isRunning ? "On deck" : "Not called";
  if (event.action?.startsWith("Completed review")) return "Review complete";
  if (event.action?.startsWith("Made final recommendation")) return "Decision ready";
  if (event.event_type === "tool_call") return "Using MCP";
  return isRunning ? "Working" : "Recorded";
}

function money(value: number | undefined): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value ?? 0);
}

function shortTime(timestamp?: string): string {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(date);
}

function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState(101);
  const [cash, setCash] = useState<CashAccount | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [runIds, setRunIds] = useState<Record<number, string>>({});
  const [runningTicketId, setRunningTicketId] = useState<number | null>(null);
  const [baselineRunId, setBaselineRunId] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<number, TicketDecision>>({});
  const [approverName, setApproverName] = useState("");
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectedTicket = tickets.find((ticket) => ticket.ticket_id === selectedTicketId);
  const currentRunId = runIds[selectedTicketId];
  const activeRunId =
    runningTicketId === selectedTicketId && currentRunId === baselineRunId
      ? undefined
      : currentRunId;
  const ticketEvents = activeRunId
    ? events.filter((event) => event.run_id === activeRunId)
    : [];
  const selectedDecision = decisions[selectedTicketId];
  const isRunning = runningTicketId === selectedTicketId;
  const openCount = tickets.filter((ticket) => ticket.is_open).length;

  async function refreshDashboard(showSpinner = false) {
    if (showSpinner) setRefreshing(true);
    try {
      const [nextTickets, nextCash, nextApprovals, nextEvents] = await Promise.all([
        request<Ticket[]>("/tickets"),
        request<CashAccount>("/cash"),
        request<{ approvals: Approval[] }>("/approvals?status=pending&limit=100"),
        fetchEvents(),
      ]);
      setTickets(nextTickets);
      setCash(nextCash);
      setApprovals(nextApprovals.approvals);
      setEvents(nextEvents);
      setRunIds(latestRunIds(nextEvents));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not reach the Campus Customs API.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void refreshDashboard();
    const interval = window.setInterval(() => void refreshDashboard(), 7000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (runningTicketId === null) return;
    let active = true;
    const poll = async () => {
      try {
        const nextEvents = await fetchEvents();
        if (!active) return;
        setEvents(nextEvents);
        setRunIds(latestRunIds(nextEvents));
      } catch {
        // The run request reports the final error; keep the last activity visible.
      }
    };
    void poll();
    const interval = window.setInterval(() => void poll(), POLL_INTERVAL);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [runningTicketId]);

  async function startAgentRun() {
    if (!selectedTicket || selectedTicket.is_resolved || runningTicketId !== null) return;
    setError("");
    setNotice("");
    setDecisions((current) => {
      const updated = { ...current };
      delete updated[selectedTicket.ticket_id];
      return updated;
    });
    setBaselineRunId(runIds[selectedTicket.ticket_id] ?? null);
    setRunningTicketId(selectedTicket.ticket_id);
    try {
      const result = await request<{ ticket_id: number; decision: TicketDecision }>(
        `/tickets/${selectedTicket.ticket_id}/run`,
        { method: "POST" },
      );
      setDecisions((current) => ({ ...current, [result.ticket_id]: result.decision }));
      setNotice(`Ticket ${result.ticket_id} review is complete.`);
      await refreshDashboard();
    } catch (cause) {
      const latest = await fetchEvents().catch(() => events);
      setEvents(latest);
      setRunIds(latestRunIds(latest));
      setError(cause instanceof Error ? cause.message : "The agent run could not be completed.");
    } finally {
      setRunningTicketId(null);
    }
  }

  async function reviewProposal(proposal: Approval, action: "approve" | "reject") {
    if (!approverName.trim()) {
      setError("Enter the approving person's name before reviewing a proposal.");
      return;
    }
    setError("");
    setNotice("");
    setReviewingId(proposal.id);
    try {
      await request(`/approvals/${proposal.id}/${action}`, {
        method: "POST",
        body: JSON.stringify({ approved_by: approverName.trim() }),
      });
      setNotice(
        action === "approve"
          ? `${proposal.action_type === "payment" ? "Payment" : "Purchase"} approved. Checking balance refreshed.`
          : "Proposal rejected. Cash was not changed.",
      );
      await refreshDashboard();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not review this proposal.");
    } finally {
      setReviewingId(null);
    }
  }

  const sortedTickets = [...tickets].sort((left, right) => {
    if (left.is_resolved !== right.is_resolved) return left.is_resolved ? 1 : -1;
    return left.ticket_id - right.ticket_id;
  });

  return (
    <div className="app-shell">
      <div className="top-stripe" aria-hidden="true" />
      <header className="masthead">
        <div className="brand-lockup">
          <div className="brand-seal" aria-hidden="true">
            <span>CC</span>
            <Sparkles size={12} strokeWidth={2.5} />
          </div>
          <div>
            <p className="eyebrow">Campus Customs / Ticket Office</p>
            <div className="brand-title">Agent desk</div>
          </div>
        </div>
        <div className="header-side">
          <div className="open-meter">
            <span className="meter-mark" aria-hidden="true">{String(openCount).padStart(2, "0")}</span>
            <span>{openCount === 1 ? "open ticket" : "open tickets"}</span>
          </div>
          <div className="cash-tile" aria-label="Checking balance">
            <div className="cash-icon"><Wallet size={18} /></div>
            <div>
              <span className="cash-caption">Checking</span>
              <strong>{cash ? money(cash.balance) : "--"}</strong>
            </div>
            {cash && <span className="cash-date">As of {cash.date}</span>}
          </div>
        </div>
      </header>

      <main className="page-wrap">
        <div className="page-heading">
          <div>
            <p className="eyebrow blue-eyebrow"><span className="heading-star">✦</span> Daily docket</p>
            <h1>What needs a hand?</h1>
            <p className="page-subtitle">Three tickets, one careful decision at a time.</p>
          </div>
          <button className="quiet-button refresh-button" type="button" onClick={() => void refreshDashboard(true)} disabled={refreshing}>
            <RefreshCw size={15} className={refreshing ? "spin" : ""} />
            <span>Refresh desk</span>
          </button>
        </div>

        {error && (
          <div className="notice notice-error" role="alert">
            <CircleAlert size={17} />
            <span>{error}</span>
            <button type="button" aria-label="Dismiss error" onClick={() => setError("")}><X size={16} /></button>
          </div>
        )}
        {notice && (
          <div className="notice notice-success" role="status">
            <CheckCircle2 size={17} />
            <span>{notice}</span>
            <button type="button" aria-label="Dismiss notice" onClick={() => setNotice("")}><X size={16} /></button>
          </div>
        )}

        <div className="desk-layout">
          <aside className="queue-column" aria-label="Ticket queue">
            <div className="section-heading queue-heading">
              <div>
                <p className="eyebrow">The queue</p>
                <h2>Tickets <span className="count-badge">{tickets.length}</span></h2>
              </div>
              <span className="queue-stamp"><span>CC</span><small>DESK<br />COPY</small></span>
            </div>
            {loading ? (
              <div className="loading-row"><LoaderCircle size={17} className="spin" /> Loading tickets</div>
            ) : (
              <div className="ticket-list">
                {sortedTickets.map((ticket, index) => {
                  const isSelected = ticket.ticket_id === selectedTicketId;
                  return (
                    <button
                      key={ticket.ticket_id}
                      className={`ticket-row ${isSelected ? "selected" : ""} ${ticket.is_resolved ? "resolved" : ""}`}
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => {
                        setSelectedTicketId(ticket.ticket_id);
                        setError("");
                        setNotice("");
                      }}
                    >
                      <span className="ticket-row-number">{String(index + 1).padStart(2, "0")}</span>
                      <span className="ticket-row-copy">
                        <span className="ticket-row-kicker">#{ticket.ticket_id} / {TICKET_TYPE[ticket.type] ?? ticket.type}</span>
                        <strong>{ticket.subject}</strong>
                        <span className="ticket-requester">{ticket.requester}</span>
                      </span>
                      <span className={`ticket-state ${ticket.is_resolved ? "state-resolved" : "state-open"}`}>
                        {ticket.is_resolved ? <BadgeCheck size={13} /> : <span className="open-dot" />}
                        {ticket.is_resolved ? "Resolved" : "Open"}
                      </span>
                    </button>
                  );
                })}
                {!loading && tickets.length === 0 && <p className="empty-note">No tickets returned by the desk API.</p>}
              </div>
            )}
            <div className="queue-footnote">
              <span className="footnote-star">✦</span>
              <span>Sorted open first<br /><small>Resolved tickets stay on file.</small></span>
            </div>
          </aside>

          <section className="case-column" aria-label="Selected ticket workspace">
            {selectedTicket ? (
              <>
                <div className="case-header">
                  <div>
                    <p className="eyebrow blue-eyebrow">Ticket {selectedTicket.ticket_id} <span className="slash">/</span> {TICKET_TYPE[selectedTicket.type] ?? selectedTicket.type}</p>
                    <h2>{selectedTicket.subject}</h2>
                    <p className="case-requester">From <strong>{selectedTicket.requester}</strong></p>
                  </div>
                  <div className="case-actions">
                    <span className={`large-status ${selectedTicket.is_resolved ? "resolved" : "open"}`}>
                      {selectedTicket.is_resolved ? <BadgeCheck size={15} /> : <Clock3 size={14} />}
                      {selectedTicket.is_resolved ? "Resolved" : "Open"}
                    </span>
                    <button className="primary-button" type="button" onClick={() => void startAgentRun()} disabled={isRunning || runningTicketId !== null || selectedTicket.is_resolved}>
                      {isRunning ? <LoaderCircle size={16} className="spin" /> : <Play size={15} fill="currentColor" />}
                      <span>{isRunning ? "Team at work" : "Run agent team"}</span>
                    </button>
                  </div>
                </div>

                {selectedTicket.is_resolved && (
                  <div className="resolved-banner"><BadgeCheck size={18} /><span>This ticket is resolved.</span><span className="resolved-ribbon">FILED</span></div>
                )}

                <div className="work-columns">
                  <section className="agent-section">
                    <div className="section-heading activity-heading">
                      <div>
                        <p className="eyebrow">Live desk</p>
                        <h3>Agent activity</h3>
                      </div>
                      <span className={`run-indicator ${isRunning ? "working" : ""}`}>
                        <span />{isRunning ? "Working" : selectedDecision ? "Review complete" : "Standing by"}
                      </span>
                    </div>
                    <div className="agent-list" aria-live="polite" aria-busy={isRunning}>
                      {AGENTS.map(({ name, role, Icon, tone }) => {
                        const agentEvents = ticketEvents.filter((event) => event.actor === name);
                        const latest = agentEvents[0];
                        const status = agentStatus(name, latest, isRunning, selectedDecision);
                        return (
                          <article className={`agent-row agent-${tone}`} key={name}>
                            <div className="agent-icon"><Icon size={17} strokeWidth={2} /></div>
                            <div className="agent-info">
                              <div className="agent-name-line"><strong>{name}</strong><span>{role}</span></div>
                              <p>{eventSummary(latest)}</p>
                              {latest?.tool_name && <code className="tool-chip">{latest.tool_name}</code>}
                              {latest?.timestamp && <span className="event-time">Updated {shortTime(latest.timestamp)}</span>}
                            </div>
                            <span className={`agent-status ${status === "Working" || status === "Using MCP" ? "status-working" : ""}`}>
                              {isRunning && (!latest || status === "Working" || status === "Using MCP") && <span className="status-pulse" />}
                              {status}
                            </span>
                          </article>
                        );
                      })}
                    </div>
                    {ticketEvents.length === 0 && !isRunning && (
                      <div className="activity-empty"><Activity size={16} /><span>No run activity recorded for this ticket yet.</span></div>
                    )}
                    {selectedDecision && (
                      <div className="decision-note">
                        <div className="decision-title"><Sparkles size={15} /><span>Boss's call</span>
                          {selectedDecision.human_approval_required && <span className="approval-needed"><ShieldCheck size={12} /> Human approval needed</span>}
                        </div>
                        <p>{selectedDecision.decision}</p>
                        {selectedDecision.rationale.length > 0 && <small>{selectedDecision.rationale[0]}</small>}
                        {selectedDecision.approval_reason && <small className="approval-reason">{selectedDecision.approval_reason}</small>}
                      </div>
                    )}
                  </section>

                  <section className="approval-section">
                    <div className="section-heading approval-heading">
                      <div>
                        <p className="eyebrow">Human review</p>
                        <h3>Approval desk <span className="count-badge">{approvals.length}</span></h3>
                      </div>
                      <ShieldCheck size={19} className="approval-icon" />
                    </div>
                    {approvals.length > 0 && (
                      <label className="reviewer-field">
                        <span>Approver name</span>
                        <input value={approverName} onChange={(event) => setApproverName(event.target.value)} placeholder="Enter your name" />
                      </label>
                    )}
                    <div className="approval-list">
                      {approvals.map((proposal) => (
                        <article className="approval-card" key={proposal.id}>
                          <div className="proposal-topline">
                            <span className={`proposal-type ${proposal.action_type}`}>
                              {proposal.action_type === "payment" ? <FileText size={13} /> : <PackageSearch size={13} />}
                              {proposal.action_type}
                            </span>
                            <span className="proposal-ticket">Ticket {proposal.ticket_id}</span>
                          </div>
                          <strong className="proposal-amount">{money(proposal.amount)}</strong>
                          <p>{proposal.description}</p>
                          {proposal.reference_type && <small className="proposal-reference">Ref: {proposal.reference_type} {proposal.reference_id}</small>}
                          <div className="approval-actions">
                            <button className="approve-button" type="button" onClick={() => void reviewProposal(proposal, "approve")} disabled={reviewingId !== null || !approverName.trim()}>
                              {reviewingId === proposal.id ? <LoaderCircle size={14} className="spin" /> : <CheckCircle2 size={14} />}
                              Approve
                            </button>
                            <button className="reject-button" type="button" onClick={() => void reviewProposal(proposal, "reject")} disabled={reviewingId !== null || !approverName.trim()}>
                              Reject
                            </button>
                          </div>
                        </article>
                      ))}
                      {approvals.length === 0 && (
                        <div className="approval-empty">
                          <div className="empty-seal"><ShieldCheck size={20} /></div>
                          <strong>Nothing waiting</strong>
                          <span>Cash changes only after a human approves a proposal.</span>
                        </div>
                      )}
                    </div>
                  </section>
                </div>
              </>
            ) : (
              <div className="case-loading"><LoaderCircle size={20} className="spin" /><span>{loading ? "Setting the desk..." : "Ticket not available."}</span></div>
            )}
          </section>
        </div>
        <footer className="desk-footer">
          <span><span className="footer-star">✦</span> Campus Customs / Desk copy</span>
          <span>API <code>{API_BASE}</code></span>
        </footer>
      </main>
    </div>
  );
}

export default App;
