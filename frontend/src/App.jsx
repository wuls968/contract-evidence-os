import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { copyText, formatCost, formatNumber, requestJson, useJson } from "./api";
import { EChart, buildAuditTrendOption, buildSimpleBarOption, buildTimelineOption, buildUsageTrendOption } from "./charts";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/audit", label: "Audit" },
  { to: "/benchmarks", label: "Benchmarks" },
  { to: "/playbooks", label: "Playbooks" },
  { to: "/collaboration", label: "Collaboration" },
  { to: "/memory", label: "Memory" },
  { to: "/mcp", label: "MCP" },
  { to: "/software", label: "Software" },
  { to: "/maintenance", label: "Maintenance" },
  { to: "/usage", label: "Usage" },
  { to: "/settings", label: "Settings" },
  { to: "/doctor", label: "Doctor" },
];

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [commandOpen, setCommandOpen] = useState(false);
  const [session, setSession] = useState(null);
  const [sessionError, setSessionError] = useState("");
  const [liveEvents, setLiveEvents] = useState({});

  useEffect(() => {
    requestJson("/auth/session")
      .then((payload) => {
        setSession(payload);
        setSessionError("");
      })
      .catch((reason) => {
        setSession(null);
        setSessionError(reason instanceof Error ? reason.message : String(reason));
      });
  }, [location.pathname]);

  useEffect(() => {
    if (!session) return undefined;
    const source = new EventSource("/events/stream", { withCredentials: true });
    const update = (name) => (event) => {
      try {
        const payload = JSON.parse(event.data);
        setLiveEvents((current) => ({ ...current, [name]: payload }));
      } catch (_error) {
        // Ignore malformed event payloads and keep the console responsive.
      }
    };
    source.addEventListener("dashboard", update("dashboard"));
    source.addEventListener("usage", update("usage"));
    source.addEventListener("maintenance", update("maintenance"));
    source.addEventListener("approvals", update("approvals"));
    source.addEventListener("audit", update("audit"));
    source.addEventListener("benchmarks", update("benchmarks"));
    return () => source.close();
  }, [session]);

  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((current) => !current);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const commandActions = useMemo(
    () => [
      { label: "Open Dashboard", path: "/dashboard" },
      { label: "Open Audit Ledger", path: "/audit" },
      { label: "Open Benchmarks", path: "/benchmarks" },
      { label: "Open Collaboration", path: "/collaboration" },
      { label: "Review Usage", path: "/usage" },
      { label: "Inspect Maintenance", path: "/maintenance" },
      { label: "Inspect MCP Surface", path: "/mcp" },
      { label: "Open Software Console", path: "/software" },
      { label: "Run Doctor", path: "/doctor" },
      { label: "Settings", path: "/settings" },
    ],
    [],
  );

  const topStatus = liveEvents.dashboard?.system?.summary || {};
  const maintenanceIncidentCount = liveEvents.maintenance?.items?.reduce(
    (count, item) => count + (item.incidents?.length ?? 0),
    0,
  );

  return (
    <div className="console-root">
      <aside className="console-nav">
        <div className="console-brand">
          <span className="console-brand-mark">CE</span>
          <div>
            <div className="console-eyebrow">Runtime OS</div>
            <h1>Contract-Evidence OS</h1>
          </div>
        </div>
        <nav>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? "nav-item nav-item-active" : "nav-item")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button className="command-button" type="button" onClick={() => setCommandOpen(true)}>
          Command Palette
          <span>Ctrl/⌘ K</span>
        </button>
      </aside>

      <main className="console-main">
        <header className="console-topbar">
          <div>
            <div className="console-eyebrow">Operator API v1</div>
            <div className="topbar-title">{location.pathname}</div>
          </div>
          <div className="status-strip">
            <StatusPill label="Mode" value={topStatus.system_mode || "idle"} />
            <StatusPill label="Queued" value={topStatus.queued_tasks ?? 0} />
            <StatusPill label="Budget pressure" value={topStatus.budget_pressure ?? 0} />
            <StatusPill label="Incidents" value={maintenanceIncidentCount ?? 0} tone={(maintenanceIncidentCount ?? 0) > 0 ? "warning" : "ok"} />
          </div>
        </header>

        <section className="console-content">
          <Routes>
            <Route path="/" element={<RedirectRoute to="/dashboard" />} />
            <Route path="/setup" element={<SetupPage />} />
            <Route path="/login" element={<LoginPage onLogin={setSession} />} />
            <Route path="/dashboard" element={<DashboardPage liveEvents={liveEvents} />} />
            <Route path="/tasks/:taskId" element={<TaskPage />} />
            <Route path="/audit" element={<AuditPage liveEvents={liveEvents} />} />
            <Route path="/benchmarks" element={<BenchmarksPage liveEvents={liveEvents} />} />
            <Route path="/playbooks" element={<PlaybooksPage />} />
            <Route path="/collaboration" element={<CollaborationPage />} />
            <Route path="/memory" element={<MemoryPage />} />
            <Route path="/memory/:taskId" element={<TaskMemoryPage />} />
            <Route path="/mcp" element={<MCPPage />} />
            <Route path="/software" element={<SoftwarePage />} />
            <Route path="/maintenance" element={<MaintenancePage />} />
            <Route path="/usage" element={<UsagePage liveEvents={liveEvents} />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/doctor" element={<DoctorPage />} />
          </Routes>
        </section>
      </main>

      <aside className="console-inspector">
        <div className="inspector-section">
          <div className="console-eyebrow">Session</div>
          {session ? (
            <>
              <h3>{session.account.display_name}</h3>
              <p>{session.account.email}</p>
              <InlineList label="Roles" items={session.roles} />
              <InlineList label="Scopes" items={session.scopes.slice(0, 6)} />
            </>
          ) : (
            <p className="muted">{sessionError || "No browser session yet."}</p>
          )}
        </div>
        <div className="inspector-section">
          <div className="console-eyebrow">Quick Copy</div>
          <CopyLine label="CLI" value="ceos --config runtime/config.local.json doctor" />
          <CopyLine label="curl" value="curl -H 'Authorization: Bearer $CEOS_OPERATOR_TOKEN' http://127.0.0.1:8080/v1/reports/system" />
          <CopyLine label="API" value="GET /v1/service/api-contract" />
        </div>
        <div className="inspector-section">
          <div className="console-eyebrow">Live Hints</div>
          <p className="muted">Setup, usage, approvals, and maintenance all stay evidence-linked. The console never bypasses the governed control plane.</p>
        </div>
      </aside>

      {commandOpen ? (
        <CommandPalette
          actions={commandActions}
          onClose={() => setCommandOpen(false)}
          onSelect={(path) => {
            setCommandOpen(false);
            startTransition(() => navigate(path));
          }}
        />
      ) : null}
    </div>
  );
}

function RedirectRoute({ to }) {
  const navigate = useNavigate();
  useEffect(() => {
    navigate(to, { replace: true });
  }, [navigate, to]);
  return null;
}

function StatusPill({ label, value, tone = "neutral" }) {
  return (
    <div className={`status-pill status-pill-${tone}`}>
      <span>{label}</span>
      <strong>{String(value)}</strong>
    </div>
  );
}

function InlineList({ label, items }) {
  return (
    <div className="inline-list">
      <span>{label}</span>
      <div>{items.join(", ") || "none"}</div>
    </div>
  );
}

function CopyLine({ label, value }) {
  return (
    <button className="copy-line" type="button" onClick={() => copyText(value)}>
      <span>{label}</span>
      <code>{value}</code>
    </button>
  );
}

function CommandPalette({ actions, onClose, onSelect }) {
  return (
    <div className="palette-backdrop" role="presentation" onClick={onClose}>
      <div className="palette" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <div className="console-eyebrow">Quick Navigation</div>
        {actions.map((action) => (
          <button key={action.path} className="palette-item" type="button" onClick={() => onSelect(action.path)}>
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function SetupPage() {
  const navigate = useNavigate();
  const { data, loading, error } = useJson("/ui/bootstrap-state");
  const [form, setForm] = useState({
    email: "admin@example.com",
    password: "",
    display_name: "Admin Operator",
    kind: "deterministic",
    baseUrl: "https://api.openai.com/v1",
    defaultModel: "gpt-4.1-mini",
    apiKey: "",
    host: "127.0.0.1",
    port: 8080,
    repoPath: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  if (loading) return <LoadingState label="Reading bootstrap state" />;
  if (data?.setup_required === false) return <ActionBanner tone="ok" title="Setup already completed" description="A bootstrap admin already exists. You can sign in instead." actionLabel="Go to login" onAction={() => navigate("/login")} />;

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setSubmitError("");
    try {
      await requestJson("/auth/bootstrap-admin", {
        method: "POST",
        body: JSON.stringify({
          email: form.email,
          password: form.password,
          display_name: form.display_name,
          provider: {
            kind: form.kind,
            base_url: form.baseUrl,
            default_model: form.defaultModel,
            api_key: form.apiKey,
          },
          service: { host: form.host, port: Number(form.port) },
          software_control_repo_path: form.repoPath,
          observability_enabled: true,
        }),
      });
      navigate("/login");
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page page-focus">
      <section className="poster-panel">
        <div className="console-eyebrow">First-run setup</div>
        <h2>Bootstrap the operator console without editing files by hand.</h2>
        <p>The setup wizard writes the local profile, generates the browser admin, and keeps file-based config compatible with the CLI and API.</p>
      </section>
      <form className="form-grid" onSubmit={handleSubmit}>
        <LabeledInput label="Admin email" value={form.email} onChange={(value) => setForm((current) => ({ ...current, email: value }))} />
        <LabeledInput label="Display name" value={form.display_name} onChange={(value) => setForm((current) => ({ ...current, display_name: value }))} />
        <LabeledInput label="Password" type="password" value={form.password} onChange={(value) => setForm((current) => ({ ...current, password: value }))} />
        <LabeledSelect label="Provider kind" value={form.kind} onChange={(value) => setForm((current) => ({ ...current, kind: value }))} options={["deterministic", "openai-compatible", "anthropic"]} />
        <LabeledInput label="Base URL" value={form.baseUrl} onChange={(value) => setForm((current) => ({ ...current, baseUrl: value }))} />
        <LabeledInput label="Default model" value={form.defaultModel} onChange={(value) => setForm((current) => ({ ...current, defaultModel: value }))} />
        <LabeledInput label="API key" type="password" value={form.apiKey} onChange={(value) => setForm((current) => ({ ...current, apiKey: value }))} />
        <LabeledInput label="Operator host" value={form.host} onChange={(value) => setForm((current) => ({ ...current, host: value }))} />
        <LabeledInput label="Operator port" value={String(form.port)} onChange={(value) => setForm((current) => ({ ...current, port: value }))} />
        <LabeledInput label="Software-control repo" value={form.repoPath} onChange={(value) => setForm((current) => ({ ...current, repoPath: value }))} />
        {error ? <ErrorBanner title="Bootstrap state unavailable" detail={error} /> : null}
        {submitError ? <ErrorBanner title="Bootstrap failed" detail={submitError} /> : null}
        <button className="primary-button" type="submit" disabled={submitting}>
          {submitting ? "Creating admin..." : "Create bootstrap admin"}
        </button>
      </form>
    </div>
  );
}

function LoginPage({ onLogin }) {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    try {
      const payload = await requestJson("/auth/login", {
        method: "POST",
        body: JSON.stringify(form),
      });
      onLogin(payload);
      navigate("/dashboard");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  return (
    <div className="page page-focus">
      <section className="poster-panel">
        <div className="console-eyebrow">Shared operator access</div>
        <h2>Sign into the governed control plane.</h2>
        <p>Browser sessions map onto the same scope model the CLI and bearer-token API already use.</p>
      </section>
      <form className="form-grid" onSubmit={handleSubmit}>
        <LabeledInput label="Email" value={form.email} onChange={(value) => setForm((current) => ({ ...current, email: value }))} />
        <LabeledInput label="Password" type="password" value={form.password} onChange={(value) => setForm((current) => ({ ...current, password: value }))} />
        {error ? <ErrorBanner title="Login failed" detail={error} /> : null}
        <button className="primary-button" type="submit">
          Sign in
        </button>
      </form>
    </div>
  );
}

function DashboardPage({ liveEvents }) {
  const { data, loading, error } = useJson("/ui/dashboard-summary");
  const [approvalModal, setApprovalModal] = useState(null);
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const payload = liveEvents.dashboard || data;

  if (loading && !payload) return <LoadingState label="Loading dashboard" />;
  if (error && !payload) return <ErrorBanner title="Dashboard unavailable" detail={error} />;
  const filteredTasks = (payload?.recent_tasks || []).filter((item) =>
    item.goal.toLowerCase().includes(deferredSearch.toLowerCase()) || item.task_id.toLowerCase().includes(deferredSearch.toLowerCase()),
  );

  return (
    <div className="page">
      <SectionHeader title="Trusted runtime overview" description="Health, queues, audit drift, benchmark posture, and recent governed work in one cockpit." />
      <div className="dense-grid">
        <Panel title="Recent tasks" subtitle="Resumable work with blockers spelled out.">
          <input className="filter-input" placeholder="Search tasks" value={search} onChange={(event) => setSearch(event.target.value)} />
          {filteredTasks.map((task) => (
            <div key={task.task_id} className="list-row">
              <div>
                <a href={`/tasks/${task.task_id}`}>{task.goal || task.task_id}</a>
                <div className="muted">{task.status} · {task.current_phase}</div>
              </div>
              {task.blocked_reason ? <span className="badge badge-warning">{task.blocked_reason}</span> : null}
            </div>
          ))}
        </Panel>
        <Panel title="Token usage trend" subtitle="Provider-level consumption across the current monitoring window.">
          <MetricRow label="Total tokens (24h)" value={formatNumber(payload?.usage?.totals?.total_tokens)} />
          <MetricRow label="Estimated cost" value={formatCost(payload?.usage?.totals?.estimated_cost)} />
          <MetricRow label="Requests" value={formatNumber(payload?.usage?.totals?.request_count)} />
          <EChart option={buildUsageTrendOption(payload?.usage?.trends || [])} height={220} />
        </Panel>
      </div>
      <div className="dense-grid">
        <Panel title="Approval and review inbox" subtitle="Every sensitive action stays audit-linked and reviewable.">
          {(payload?.approvals || []).length === 0 ? <EmptyState title="No pending approvals" description="Governed actions are currently flowing without intervention." /> : null}
          {(payload?.approvals || []).map((approval) => (
            <div key={approval.request_id} className="approval-row">
              <div>
                <strong>{approval.action_summary}</strong>
                <div className="muted">{approval.reason}</div>
              </div>
              <button className="secondary-button" type="button" onClick={() => setApprovalModal(approval)}>
                Review
              </button>
            </div>
          ))}
        </Panel>
        <Panel title="Trust posture" subtitle="Audit activity, benchmark readiness, and maintenance incidents.">
          <MetricRow label="Incidents" value={formatNumber(payload?.health_badges?.maintenance_incidents)} />
          <MetricRow label="Setup required" value={String(payload?.health_badges?.setup_required)} />
          <MetricRow label="Provider fallback" value={String(payload?.health_badges?.provider_fallback)} />
          <MetricRow label="Audit events" value={formatNumber(payload?.audit?.total_events)} />
          <MetricRow label="Benchmark suites" value={formatNumber(payload?.benchmarks?.suites?.length)} />
          <MetricRow label="Collaborators" value={formatNumber(payload?.collaboration?.user_count)} />
        </Panel>
      </div>
      <div className="dense-grid">
        <Panel title="Audit trend" subtitle="Append-only activity over time.">
          <EChart option={buildAuditTrendOption(liveEvents.audit?.trend?.points || [])} height={220} />
        </Panel>
        <Panel title="Provider distribution" subtitle="High-level mix by provider within the active window.">
          <UsageBar providers={payload?.usage?.providers || []} />
        </Panel>
      </div>
      {approvalModal ? <ApprovalModal approval={approvalModal} onClose={() => setApprovalModal(null)} /> : null}
    </div>
  );
}

function TaskPage() {
  const { taskId } = useParams();
  const { data, loading, error } = useJson(`/ui/tasks/${taskId}`);
  if (loading) return <LoadingState label="Loading task cockpit" />;
  if (error) return <ErrorBanner title="Task cockpit unavailable" detail={error} />;
  return (
    <div className="page">
      <SectionHeader title={data.task.request.goal || data.task.task_id} description="Cockpit view: status, continuity, usage, memory, replay, and approvals." />
      <div className="dense-grid">
        <Panel title="Status" subtitle="Current execution posture.">
          <MetricRow label="Status" value={data.status.status} />
          <MetricRow label="Phase" value={data.status.current_phase} />
          <MetricRow label="Checkpoint" value={data.status.latest_checkpoint_id || "none"} />
        </Panel>
        <Panel title="Usage" subtitle="Provider consumption for this task.">
          <MetricRow label="Tokens" value={formatNumber(data.usage.total_tokens)} />
          <MetricRow label="Estimated cost" value={formatCost(data.usage.estimated_cost)} />
          <MetricRow label="Requests" value={formatNumber(data.usage.request_count)} />
        </Panel>
      </div>
      <div className="dense-grid">
        <Panel title="Task timeline" subtitle="Contract, checkpoints, approvals, receipts, and provider usage in one lane view.">
          <EChart option={buildTimelineOption(data.timeline)} height={260} />
        </Panel>
        <Panel title="Collaboration" subtitle="Who owns this work and where review is blocked.">
          <MetricRow label="Owner" value={data.collaboration.owner || "unassigned"} />
          <MetricRow label="Reviewer" value={data.collaboration.reviewer || "unassigned"} />
          <MetricRow label="Waiting for" value={data.collaboration.waiting_for || "nobody"} />
          <MetricRow label="Approval assignee" value={data.collaboration.approval_assignee || "none"} />
        </Panel>
      </div>
      <div className="dense-grid">
        <Panel title="Open questions" subtitle="Unfinished ambiguity with continuity context.">
          {(data.open_questions || []).length ? data.open_questions.map((item) => <ListItem key={item.question_id || item.question}>{item.question || JSON.stringify(item)}</ListItem>) : <EmptyState title="No open questions" description="The current task state is internally coherent." />}
        </Panel>
        <Panel title="Approvals" subtitle="Task-scoped intervention queue.">
          {(data.approvals || []).length ? data.approvals.map((item) => <ListItem key={item.request_id}>{item.action_summary}</ListItem>) : <EmptyState title="No pending approvals" description="No manual gate is currently blocking this task." />}
        </Panel>
      </div>
      <div className="dense-grid">
        <Panel title="Evidence trace" subtitle="Source → span → claim → validation path.">
          <EvidenceTracePanel trace={data.evidence_trace} />
        </Panel>
        <Panel title="Trusted playbook" subtitle="The controlled delivery path for this task.">
          {(data.playbook?.steps || []).map((step) => (
            <div key={step.step_id} className="list-row">
              <div>
                <strong>{step.title}</strong>
                <div className="muted">{step.description}</div>
              </div>
              <span className="badge">{step.status}</span>
            </div>
          ))}
        </Panel>
      </div>
      <Panel title="Memory kernel" subtitle="Timeline and project-state view from AMOS.">
        <pre className="code-block">{JSON.stringify(data.memory, null, 2)}</pre>
      </Panel>
    </div>
  );
}

function MemoryPage() {
  const { data, loading, error } = useJson("/ui/memory/overview");
  if (loading) return <LoadingState label="Loading memory overview" />;
  if (error) return <ErrorBanner title="Memory overview unavailable" detail={error} />;
  return (
    <div className="page">
      <SectionHeader title="AMOS memory OS" description="Timeline, project state, and maintenance posture per task." />
      {data.items.map((item) => (
        <Panel key={item.task_id} title={item.task_id} subtitle="Timeline + project state">
          <MetricRow label="Subject" value={item.project_state_view.subject} />
          <MetricRow label="Predicate" value={item.project_state_view.predicate} />
          <MetricRow label="Maintenance mode" value={item.maintenance_mode.mode} />
          <a href={`/memory/${item.task_id}`}>Open memory detail</a>
        </Panel>
      ))}
    </div>
  );
}

function TaskMemoryPage() {
  const { taskId } = useParams();
  const { data, loading, error } = useJson(`/ui/memory/${taskId}`);
  if (loading) return <LoadingState label="Loading task memory" />;
  if (error) return <ErrorBanner title="Task memory unavailable" detail={error} />;
  return (
    <div className="page">
      <SectionHeader title={`Memory ${taskId}`} description="Kernel receipts, evidence packs, timeline, and repair policy." />
      <pre className="code-block">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}

function SoftwarePage() {
  const { data, loading, error } = useJson("/ui/software/overview");
  if (loading) return <LoadingState label="Loading software control" />;
  if (error) return <ErrorBanner title="Software control unavailable" detail={error} />;
  return (
    <div className="page">
      <SectionHeader title="Software control fabric" description="Harnesses, manifests, macros, failure clusters, and recovery hints." />
      <div className="dense-grid">
        <Panel title="Harnesses" subtitle="Governed app entry points.">
          {data.harnesses.map((item) => (
            <ListItem key={item.harness_id}>{item.software_name} · {item.executable_name}</ListItem>
          ))}
        </Panel>
        <Panel title="Failure clusters" subtitle="Grouped failure patterns across harness runs.">
          {(data.failure_clusters || []).map((item) => <ListItem key={item.cluster_id}>{item.title || item.cluster_id}</ListItem>)}
        </Panel>
      </div>
      <Panel title="Recovery hints" subtitle="Operator-safe remediation guidance.">
        {(data.recovery_hints || []).map((item) => <ListItem key={item.hint_id}>{item.summary || item.hint_id}</ListItem>)}
      </Panel>
    </div>
  );
}

function MaintenancePage() {
  const { data, loading, error } = useJson("/ui/maintenance/overview");
  if (loading) return <LoadingState label="Loading maintenance center" />;
  if (error) return <ErrorBanner title="Maintenance center unavailable" detail={error} />;
  return (
    <div className="page">
      <SectionHeader title="Resident maintenance daemon" description="Workers, incidents, recommendations, daemon runs, and rollouts." />
      {data.items.map((item) => (
        <Panel key={item.task_id} title={item.task_id} subtitle={`Mode: ${item.mode.mode}`}>
          <MetricRow label="Incidents" value={formatNumber(item.incidents.length)} />
          <MetricRow label="Daemon runs" value={formatNumber(item.daemon.daemon.runs.length)} />
          <MetricRow label="Recommendations" value={formatNumber(item.recommendations.recommended_actions?.length || 0)} />
        </Panel>
      ))}
    </div>
  );
}

function UsagePage({ liveEvents }) {
  const [window, setWindow] = useState("24h");
  const { data, loading, error } = useJson(`/usage/summary?window=${window}`, { dependencies: [window] });
  const payload = liveEvents.usage || data;
  if (loading && !payload) return <LoadingState label="Loading usage" />;
  if (error && !payload) return <ErrorBanner title="Usage monitor unavailable" detail={error} />;
  return (
    <div className="page">
      <SectionHeader title="Token and cost monitor" description="Task + provider windows with cost estimates, spikes, and fallback hints." />
      <div className="toolbar">
        {["1h", "24h", "7d"].map((option) => (
          <button key={option} className={window === option ? "secondary-button secondary-button-active" : "secondary-button"} type="button" onClick={() => setWindow(option)}>
            {option}
          </button>
        ))}
      </div>
      <div className="dense-grid">
        <Panel title="Totals" subtitle="Rolling usage window">
          <MetricRow label="Tokens" value={formatNumber(payload?.totals?.total_tokens)} />
          <MetricRow label="Estimated cost" value={formatCost(payload?.totals?.estimated_cost)} />
          <MetricRow label="Requests" value={formatNumber(payload?.totals?.request_count)} />
        </Panel>
        <Panel title="Provider trend" subtitle="Stacked provider activity over time">
          <EChart option={buildUsageTrendOption(payload?.trends || [])} height={240} />
        </Panel>
      </div>
      <Panel title="Tasks" subtitle="Sortable task-level usage rows">
        {(payload?.tasks || []).map((item) => (
          <div key={item.task_id} className="list-row">
            <a href={`/tasks/${item.task_id}`}>{item.task_id}</a>
            <span>{formatNumber(item.total_tokens)} tokens</span>
            <span>{formatCost(item.estimated_cost)}</span>
          </div>
        ))}
      </Panel>
    </div>
  );
}

function AuditPage({ liveEvents }) {
  const { data, loading, error } = useJson("/ui/audit/overview");
  const payload = liveEvents.audit || data;
  if (loading && !payload) return <LoadingState label="Loading audit ledger" />;
  if (error && !payload) return <ErrorBanner title="Audit ledger unavailable" detail={error} />;
  return (
    <div className="page">
      <SectionHeader title="Audit ledger" description="Append-only operator, runtime, and evidence activity with trend visibility." />
      <div className="dense-grid">
        <Panel title="Audit activity trend" subtitle="Hourly view across the current runtime history.">
          <EChart option={buildAuditTrendOption(payload?.trend?.points || [])} height={260} />
        </Panel>
        <Panel title="Ledger summary" subtitle="Why the runtime is trustworthy at a glance.">
          <MetricRow label="Total events" value={formatNumber(payload?.summary?.total_events)} />
          <MetricRow label="Bundles" value={formatNumber(payload?.bundles?.length)} />
          <MetricRow label="Recent entries" value={formatNumber(payload?.items?.length)} />
        </Panel>
      </div>
      <Panel title="Recent audit entries" subtitle="Human-readable events with linked evidence and related ids.">
        {(payload?.items || []).slice(-20).reverse().map((item) => (
          <div key={item.entry_id} className="list-row">
            <div>
              <strong>{item.event_type}</strong>
              <div className="muted">{item.summary}</div>
            </div>
            <div className="stacked-meta">
              <span>{item.actor}</span>
              <span>{item.status}</span>
            </div>
          </div>
        ))}
      </Panel>
    </div>
  );
}

function BenchmarksPage({ liveEvents }) {
  const { data, loading, error } = useJson("/ui/benchmarks/overview");
  const payload = liveEvents.benchmarks || data;
  if (loading && !payload) return <LoadingState label="Loading benchmarks" />;
  if (error && !payload) return <ErrorBanner title="Benchmarks unavailable" detail={error} />;
  const summary = payload?.summary || {};
  return (
    <div className="page">
      <SectionHeader title="Benchmarks and reproducibility" description="Benchmark suites, latest runs, and repro-eval posture for the trusted runtime." />
      <div className="dense-grid">
        <Panel title="Benchmark suites" subtitle="Structured suites are ready for reproducible evaluation.">
          <MetricRow label="Suites" value={formatNumber(summary?.suites?.length)} />
          <MetricRow label="Latest runs" value={formatNumber(summary?.latest_runs?.length)} />
          <MetricRow label="Repro runs" value={formatNumber(summary?.repro_runs?.length)} />
        </Panel>
        <Panel title="Run scores" subtitle="Compact view of evaluation and canary-derived runs.">
          <EChart option={buildSimpleBarOption(summary?.latest_runs || [], "score", "case_id")} height={260} />
        </Panel>
      </div>
      <Panel title="Suites" subtitle="Each suite is evidence- and audit-friendly.">
        {(summary?.suites || []).map((suite) => (
          <ListItem key={suite.suite_id}>{suite.title} · {suite.benchmark_kind}</ListItem>
        ))}
      </Panel>
    </div>
  );
}

function PlaybooksPage() {
  const { data, loading, error } = useJson("/ui/playbooks/overview");
  if (loading) return <LoadingState label="Loading playbooks" />;
  if (error) return <ErrorBanner title="Playbooks unavailable" detail={error} />;
  return (
    <div className="page">
      <SectionHeader title="Trusted playbooks" description="Productized execution patterns with checkpoint, evidence, and human review requirements." />
      {(data.items || []).map((playbook) => (
        <Panel key={playbook.playbook_id} title={playbook.title} subtitle={playbook.rationale}>
          {(playbook.steps || []).map((step) => (
            <div key={step.step_id} className="list-row">
              <div>
                <strong>{step.title}</strong>
                <div className="muted">{step.description}</div>
              </div>
              <span className="badge">{step.status}</span>
            </div>
          ))}
        </Panel>
      ))}
    </div>
  );
}

function CollaborationPage() {
  const { data, loading, error, setData } = useJson("/ui/collaboration/overview");
  const [actionError, setActionError] = useState("");
  if (loading) return <LoadingState label="Loading collaboration plane" />;
  if (error) return <ErrorBanner title="Collaboration plane unavailable" detail={error} />;

  async function createUser(event) {
    event.preventDefault();
    setActionError("");
    const form = new FormData(event.currentTarget);
    try {
      const payload = await requestJson("/auth/users", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
          display_name: form.get("display_name"),
          role_name: form.get("role_name"),
        }),
      });
      setData((current) => ({
        ...(current || {}),
        users: [...(current?.users || []), payload.account],
        role_bindings: [...(current?.role_bindings || []), ...(payload.roles || [])],
      }));
      event.currentTarget.reset();
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function inviteUser(event) {
    event.preventDefault();
    setActionError("");
    const form = new FormData(event.currentTarget);
    try {
      const payload = await requestJson("/auth/invitations", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          role_name: form.get("role_name"),
          invited_by: form.get("invited_by"),
        }),
      });
      setData((current) => ({ ...(current || {}), invitations: [...(current?.invitations || []), payload.invitation] }));
      event.currentTarget.reset();
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  return (
    <div className="page">
      <SectionHeader title="Collaboration control plane" description="Users, roles, sessions, invitations, and task ownership for small-team self-hosting." />
      <div className="dense-grid">
        <Panel title="Users and roles" subtitle="Role-bound scope model for admins, operators, reviewers, and viewers.">
          {(data.users || []).map((user) => (
            <div key={user.user_id} className="list-row">
              <div>
                <strong>{user.display_name}</strong>
                <div className="muted">{user.email}</div>
              </div>
              <span className="badge">{(data.role_bindings || []).find((binding) => binding.user_id === user.user_id)?.role_name || "viewer"}</span>
            </div>
          ))}
        </Panel>
        <Panel title="Active sessions" subtitle="Current browser sessions remain audit-visible.">
          {(data.sessions || []).map((session) => (
            <ListItem key={session.session_id}>{session.user_id} · {session.status}</ListItem>
          ))}
        </Panel>
      </div>
      <div className="dense-grid">
        <Panel title="Create local user" subtitle="Bootstrap reviewers and operators without leaving the dashboard.">
          <form className="form-grid" onSubmit={createUser}>
            <LabeledInput label="Email" name="email" defaultValue="" />
            <LabeledInput label="Display name" name="display_name" defaultValue="" />
            <LabeledInput label="Password" name="password" type="password" defaultValue="" />
            <LabeledSelect label="Role" defaultValue="reviewer" options={["admin", "operator", "reviewer", "viewer"]} name="role_name" />
            <button className="primary-button" type="submit">Create user</button>
          </form>
          {actionError ? <ErrorBanner title="Action failed" detail={actionError} /> : null}
        </Panel>
        <Panel title="Invite collaborator" subtitle="Track invitation bootstrap flow for small teams.">
          <form className="form-grid" onSubmit={inviteUser}>
            <LabeledInput label="Email" name="email" defaultValue="" />
            <LabeledInput label="Invited by" name="invited_by" defaultValue="admin@example.com" />
            <LabeledSelect label="Role" defaultValue="viewer" options={["operator", "reviewer", "viewer"]} name="role_name" />
            <button className="primary-button" type="submit">Create invitation</button>
          </form>
        </Panel>
      </div>
      <Panel title="Task collaboration bindings" subtitle="Owner, reviewer, watchers, and blocked state per task.">
        {(data.task_bindings || []).map((item) => (
          <div key={item.binding_id} className="list-row">
            <div>
              <strong>{item.task_id}</strong>
              <div className="muted">Owner {item.owner} · Reviewer {item.reviewer}</div>
            </div>
            <span className="badge">{item.waiting_for || "ready"}</span>
          </div>
        ))}
      </Panel>
    </div>
  );
}

function MCPPage() {
  const { data, loading, error, setData } = useJson("/ui/mcp/overview");
  const [actionError, setActionError] = useState("");
  if (loading) return <LoadingState label="Loading MCP runtime surface" />;
  if (error) return <ErrorBanner title="MCP runtime unavailable" detail={error} />;

  async function registerServer(event) {
    event.preventDefault();
    setActionError("");
    const form = new FormData(event.currentTarget);
    try {
      const payload = await requestJson("/ui/mcp/servers", {
        method: "POST",
        body: JSON.stringify({
          display_name: form.get("display_name"),
          transport: form.get("transport"),
          endpoint: form.get("endpoint"),
          direction: form.get("direction"),
        }),
      });
      setData((current) => ({ ...(current || {}), connected_servers: [...(current?.connected_servers || []), payload.server] }));
      event.currentTarget.reset();
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  return (
    <div className="page">
      <SectionHeader title="MCP runtime surface" description="First-class MCP server and client registry with governed invocations and schema linkage." />
      <div className="dense-grid">
        <Panel title="Built-in server surface" subtitle="CEOS capabilities exposed as governed MCP tools.">
          {(data.server_surface?.tools || []).map((tool) => (
            <div key={tool.tool_id} className="list-row">
              <div>
                <strong>{tool.display_name}</strong>
                <div className="muted">{tool.description}</div>
              </div>
              <span className="badge">{tool.permission_mode}</span>
            </div>
          ))}
        </Panel>
        <Panel title="Schema registry" subtitle="Structured schemas behind trusted runtime and MCP descriptors.">
          {(data.schema_registry?.items || []).slice(0, 8).map((item) => (
            <ListItem key={item.schema_id}>{item.title}</ListItem>
          ))}
        </Panel>
      </div>
      <div className="dense-grid">
        <Panel title="Connected servers" subtitle="Client-side MCP registry under governance and audit.">
          {(data.connected_servers || []).length ? (data.connected_servers || []).map((server) => (
            <ListItem key={server.server_id}>{server.display_name} · {server.transport}</ListItem>
          )) : <EmptyState title="No external MCP servers yet" description="Register MCP client surfaces here without bypassing the control plane." />}
        </Panel>
        <Panel title="Register MCP server" subtitle="Add a real MCP endpoint to the trusted runtime registry.">
          <form className="form-grid" onSubmit={registerServer}>
            <LabeledInput label="Display name" name="display_name" defaultValue="Contracts MCP" />
            <LabeledInput label="Transport" name="transport" defaultValue="stdio" />
            <LabeledInput label="Endpoint" name="endpoint" defaultValue="python -m contracts_mcp" />
            <LabeledInput label="Direction" name="direction" defaultValue="client" />
            <button className="primary-button" type="submit">Register server</button>
          </form>
          {actionError ? <ErrorBanner title="Registration failed" detail={actionError} /> : null}
        </Panel>
      </div>
      <Panel title="Recent invocations" subtitle="Permission decisions and invocation receipts stay linked.">
        {(data.recent_invocations || []).map((item) => (
          <div key={item.invocation_id} className="list-row">
            <div>
              <strong>{item.tool_name}</strong>
              <div className="muted">{item.result_summary}</div>
            </div>
            <span className="badge">{item.status}</span>
          </div>
        ))}
      </Panel>
    </div>
  );
}

function SettingsPage() {
  const { data, loading, error, setData } = useJson("/config/effective");
  const { data: presets } = useJson("/auth/oidc/presets");
  const { data: providers, setData: setProviders } = useJson("/auth/oidc/providers");
  const [providerTest, setProviderTest] = useState(null);
  const [oidcTest, setOidcTest] = useState(null);
  const [saveState, setSaveState] = useState("");

  if (loading) return <LoadingState label="Loading settings" />;
  if (error) return <ErrorBanner title="Settings unavailable" detail={error} />;

  async function saveProvider(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = await requestJson("/config/update", {
      method: "POST",
      body: JSON.stringify({
        provider: {
          kind: form.get("kind"),
          base_url: form.get("base_url"),
          default_model: form.get("default_model"),
          api_key: form.get("api_key"),
        },
      }),
    });
    setData(payload);
    setSaveState("Provider settings saved.");
  }

  async function testProvider() {
    const payload = await requestJson("/config/test-provider", {
      method: "POST",
      body: JSON.stringify({}),
    });
    setProviderTest(payload);
  }

  async function saveOidcProvider(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = await requestJson("/auth/oidc/providers", {
      method: "POST",
      body: JSON.stringify({
        display_name: form.get("display_name"),
        issuer: form.get("issuer"),
        client_id: form.get("client_id"),
        client_secret: form.get("client_secret"),
        authorize_url: form.get("authorize_url"),
        token_url: form.get("token_url"),
        userinfo_url: form.get("userinfo_url"),
        scopes: String(form.get("scopes") || "openid email profile").split(/\s+/).filter(Boolean),
        enabled: true,
      }),
    });
    setProviders((current) => ({ ...(current || {}), items: [...(current?.items || []), payload.provider] }));
    setSaveState("OIDC provider saved.");
  }

  async function testOidcPreset(preset) {
    const payload = await requestJson("/config/test-oidc", {
      method: "POST",
      body: JSON.stringify({
        provider_id: preset.preset_name,
        display_name: preset.display_name,
        client_id: "example-client-id",
        authorize_url: preset.authorize_url,
        token_url: preset.token_url,
        userinfo_url: preset.userinfo_url,
      }),
    });
    setOidcTest(payload);
  }

  return (
    <div className="page">
      <SectionHeader title="Settings and config center" description="Effective config, environment overrides, provider diagnostics, and OIDC presets." />
      <div className="dense-grid">
        <Panel title="Effective runtime config" subtitle="File-compatible config remains the source-compatible path.">
          <pre className="code-block">{JSON.stringify(data.effective, null, 2)}</pre>
        </Panel>
        <Panel title="Provider" subtitle="Live provider, fallback, and connectivity.">
          <form className="form-grid" onSubmit={saveProvider}>
            <LabeledInput label="Kind" name="kind" defaultValue={data.effective.provider.kind} />
            <LabeledInput label="Base URL" name="base_url" defaultValue={data.effective.provider.base_url || data.effective.provider.resolved_base_url} />
            <LabeledInput label="Default model" name="default_model" defaultValue={data.effective.provider.default_model} />
            <LabeledInput label="API key" name="api_key" type="password" defaultValue="" />
            <div className="button-row">
              <button className="primary-button" type="submit">Save provider</button>
              <button className="secondary-button" type="button" onClick={testProvider}>Test connection</button>
            </div>
          </form>
          {saveState ? <ActionBanner tone="ok" title={saveState} description="Runtime file config and env overrides have been updated." /> : null}
          {providerTest ? <pre className="code-block">{JSON.stringify(providerTest, null, 2)}</pre> : null}
        </Panel>
      </div>
      <Panel title="OIDC presets" subtitle="Generic OIDC with GitHub and Google examples.">
        {(presets?.items || []).map((item) => (
          <div key={item.preset_name} className="list-row">
            <div>
              <strong>{item.display_name}</strong>
              <div className="muted">{item.authorize_url}</div>
            </div>
            <button className="secondary-button" type="button" onClick={() => testOidcPreset(item)}>
              Test preset
            </button>
          </div>
        ))}
      </Panel>
      <div className="dense-grid">
        <Panel title="Configured OIDC providers" subtitle="Shared-user auth can stay local or grow into generic OIDC.">
          {(providers?.items || []).length ? (providers.items || []).map((item) => (
            <ListItem key={item.provider_id}>{item.display_name} · {item.issuer}</ListItem>
          )) : <EmptyState title="No OIDC providers yet" description="Local accounts remain the default bootstrap path." />}
          {oidcTest ? <pre className="code-block">{JSON.stringify(oidcTest, null, 2)}</pre> : null}
        </Panel>
        <Panel title="Add OIDC provider" subtitle="Save generic OIDC config without leaving the console.">
          <form className="form-grid" onSubmit={saveOidcProvider}>
            <LabeledInput label="Display name" name="display_name" defaultValue="GitHub OIDC" />
            <LabeledInput label="Issuer" name="issuer" defaultValue="https://github.com" />
            <LabeledInput label="Client ID" name="client_id" defaultValue="" />
            <LabeledInput label="Client secret" name="client_secret" type="password" defaultValue="" />
            <LabeledInput label="Authorize URL" name="authorize_url" defaultValue="https://github.com/login/oauth/authorize" />
            <LabeledInput label="Token URL" name="token_url" defaultValue="https://github.com/login/oauth/access_token" />
            <LabeledInput label="Userinfo URL" name="userinfo_url" defaultValue="https://api.github.com/user" />
            <LabeledInput label="Scopes" name="scopes" defaultValue="read:user user:email" />
            <button className="primary-button" type="submit">Save OIDC provider</button>
          </form>
        </Panel>
      </div>
    </div>
  );
}

function DoctorPage() {
  const { data, loading, error } = useJson("/ui/doctor");
  if (loading) return <LoadingState label="Running system doctor" />;
  if (error) return <ErrorBanner title="Doctor unavailable" detail={error} />;
  return (
    <div className="page">
      <SectionHeader title="Trust doctor" description="Startup, provider, auth, audit, and reproducibility diagnostics in one place." />
      <div className="dense-grid">
        <Panel title="Startup validation" subtitle="What blocks launch or degrades service.">
          <pre className="code-block">{JSON.stringify(data.startup, null, 2)}</pre>
        </Panel>
        <Panel title="Provider check" subtitle="Live provider connectivity or deterministic fallback diagnostics.">
          <pre className="code-block">{JSON.stringify(data.provider_check, null, 2)}</pre>
        </Panel>
      </div>
      <div className="dense-grid">
        <Panel title="Audit ledger health" subtitle="Append-only trust state should never silently disappear.">
          <MetricRow label="Status" value={data.audit_ledger.status} />
          <MetricRow label="Events" value={formatNumber(data.audit_ledger.event_count)} />
          <MetricRow label="OIDC readiness" value={data.oidc_readiness.status} />
        </Panel>
        <Panel title="Benchmark readiness" subtitle="Reproducibility posture for the trusted runtime.">
          <MetricRow label="Status" value={data.benchmark_reproducibility.status} />
          <MetricRow label="Suites" value={formatNumber(data.benchmark_reproducibility.suite_count)} />
          <MetricRow label="Runs" value={formatNumber(data.benchmark_reproducibility.run_count)} />
          <MetricRow label="Repro runs" value={formatNumber(data.benchmark_reproducibility.repro_run_count)} />
        </Panel>
      </div>
      <Panel title="Config snapshot" subtitle="Effective config with env visibility.">
        <pre className="code-block">{JSON.stringify(data.config, null, 2)}</pre>
      </Panel>
    </div>
  );
}

function ApprovalModal({ approval, onClose }) {
  const [rationale, setRationale] = useState("");
  const [error, setError] = useState("");

  async function decide(status) {
    try {
      await requestJson(`/ui/approvals/${approval.request_id}/decision`, {
        method: "POST",
        body: JSON.stringify({ status, rationale }),
      });
      onClose();
      window.location.reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  return (
    <div className="palette-backdrop" role="presentation" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <h3>{approval.action_summary}</h3>
        <p>{approval.reason}</p>
        <textarea className="filter-input textarea" value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Add rationale for the audit trail" />
        {error ? <ErrorBanner title="Decision failed" detail={error} /> : null}
        <div className="button-row">
          <button className="primary-button" type="button" onClick={() => decide("approved")}>Approve</button>
          <button className="secondary-button" type="button" onClick={() => decide("denied")}>Deny</button>
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ title, description }) {
  return (
    <div className="section-header">
      <div className="console-eyebrow">UX console</div>
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  );
}

function Panel({ title, subtitle, children }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}

function MetricRow({ label, value }) {
  return (
    <div className="metric-row">
      <span>{label}</span>
      <strong>{String(value)}</strong>
    </div>
  );
}

function UsageBar({ providers }) {
  const total = providers.reduce((sum, provider) => sum + Number(provider.total_tokens || 0), 0) || 1;
  return (
    <div className="usage-stack">
      {providers.map((provider) => (
        <div
          key={provider.provider_name}
          className="usage-segment"
          style={{ width: `${(Number(provider.total_tokens || 0) / total) * 100}%` }}
          title={`${provider.provider_name}: ${provider.total_tokens} tokens`}
        >
          <span>{provider.provider_name}</span>
        </div>
      ))}
    </div>
  );
}

function EvidenceTracePanel({ trace }) {
  return (
    <div className="trace-grid">
      <div>
        <div className="console-eyebrow">Sources</div>
        {(trace?.sources || []).slice(0, 4).map((source) => (
          <div key={source.source_id} className="list-item">
            <strong>{source.source_type}</strong>
            <div className="muted">{source.locator}</div>
          </div>
        ))}
      </div>
      <div>
        <div className="console-eyebrow">Spans</div>
        {(trace?.spans || []).slice(0, 4).map((span) => (
          <div key={span.span_id} className="list-item">
            <strong>{span.label}</strong>
            <div className="muted">{span.text}</div>
          </div>
        ))}
      </div>
      <div>
        <div className="console-eyebrow">Claims & validation</div>
        {(trace?.claims || []).slice(0, 4).map((claim) => (
          <div key={claim.claim_id} className="list-item">
            <strong>{claim.claim_type}</strong>
            <div className="muted">{claim.statement}</div>
          </div>
        ))}
        {(trace?.validations || []).slice(0, 1).map((validation) => (
          <div key={validation.report_id} className="list-item">
            <strong>{validation.status}</strong>
            <div className="muted">{(validation.findings || []).join("; ")}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LoadingState({ label }) {
  return (
    <div className="page">
      <ActionBanner tone="neutral" title={label} description="The console is assembling governed runtime state." />
    </div>
  );
}

function EmptyState({ title, description }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

function ErrorBanner({ title, detail }) {
  return <ActionBanner tone="warning" title={title} description={detail} />;
}

function ActionBanner({ title, description, tone = "neutral", actionLabel, onAction }) {
  return (
    <div className={`action-banner action-banner-${tone}`}>
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
      {actionLabel ? <button className="secondary-button" type="button" onClick={onAction}>{actionLabel}</button> : null}
    </div>
  );
}

function LabeledInput({ label, type = "text", value, defaultValue, onChange, ...props }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={value} defaultValue={defaultValue} onChange={onChange ? (event) => onChange(event.target.value) : undefined} {...props} />
    </label>
  );
}

function LabeledSelect({ label, value, defaultValue, onChange, options, ...props }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select
        value={value}
        defaultValue={defaultValue}
        onChange={onChange ? (event) => onChange(event.target.value) : undefined}
        {...props}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function ListItem({ children }) {
  return <div className="list-item">{children}</div>;
}
