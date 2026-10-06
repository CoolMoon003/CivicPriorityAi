import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ArrowLeft, ClipboardList, Clock3, Radar, ShieldCheck, Users, X } from "lucide-react";
import "./App.css";
import { getDashboard, getComplaints, getPriorities, getCompletedRepairs, getTechnicians, assignTechnician as apiAssignTechnician, deleteComplaint as apiDeleteComplaint, updateComplaintStatus as apiUpdateStatus } from "./api.js";
import { Sidebar } from "./components/Sidebar.jsx";
import { TopBar } from "./components/TopBar.jsx";
import { StatCard } from "./components/StatCard.jsx";
import { MapPanel } from "./components/MapPanel.jsx";
import { PriorityQueue } from "./components/PriorityQueue.jsx";
import { ComplaintDetail } from "./components/ComplaintDetail.jsx";
import { TechnicianPanel } from "./components/TechnicianPanel.jsx";
import { ActivityFeed } from "./components/ActivityFeed.jsx";
import { AnalyticsPanel } from "./components/AnalyticsPanel.jsx";
import { RepairPipeline } from "./components/RepairPipeline.jsx";
import { CompletedRepairs } from "./components/CompletedRepairs.jsx";
import { BudgetOptimizerPanel } from "./components/BudgetOptimizerPanel.jsx";
import { CitizenDashboard } from "./pages/CitizenDashboard.jsx";
import { RoleSelection } from "./pages/RoleSelection.jsx";
import { TechnicianDashboard } from "./pages/TechnicianDashboard.jsx";

function roleFromHash() {
  const role = window.location.hash.replace(/^#\/?/, "").toLowerCase();
  return ["citizen", "admin", "technician"].includes(role) ? role : "roles";
}

function App() {
  // A fresh page load always starts at the role picker; role hashes are for in-session navigation only.
  const [view, setView] = useState("roles");
  const [dashboard, setDashboard] = useState(null);
  const [complaints, setComplaints] = useState([]);
  const [activePriorityItems, setActivePriorityItems] = useState([]);
  const [completedRepairs, setCompletedRepairs] = useState([]);
  const [technicians, setTechnicians] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [connected, setConnected] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [activeSection, setActiveSection] = useState("overview");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [priorityFilter, setPriorityFilter] = useState("ALL");
  const sectionRefs = useRef({});

  function selectRole(role) {
    setView(role);
    setError("");
    setSelectedId(null);
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#/${role}`);
  }

  function switchRole() {
    setView("roles");
    setSelectedId(null);
    setError("");
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#/roles`);
  }

  useEffect(() => {
    const onHashChange = () => setView(roleFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const loadAll = useCallback(async (background = false) => {
    if (background) setRefreshing(true);
    else setLoading(true);
    try {
      const [dashboardData, complaintsData, techniciansData, prioritiesData, completedRepairsData] = await Promise.all([
        getDashboard(), getComplaints(), getTechnicians(), getPriorities(), getCompletedRepairs(),
      ]);
      setDashboard(dashboardData);
      const priorityById = new Map((prioritiesData.items || []).map((item) => [item.complaint_id, item]));
      const next = (complaintsData.complaints || []).map((complaint) => {
        const evidence = priorityById.get(complaint.id);
        return evidence ? { ...complaint, priority: { ...complaint.priority,
          score: evidence.priority_score, level: evidence.priority_level,
          recurrence_count: evidence.recurrence_count, components: evidence.components,
          explanations: evidence.explanations }, ai_prediction: evidence.ai_prediction } : complaint;
      });
      setComplaints((previous) => sameComplaints(previous, next) ? previous : next);
      setActivePriorityItems((prioritiesData.items || []).map((item) => ({
        id: item.complaint_id,
        location: item.location,
        road: item.road,
        damage: item.damage,
        priority: { score: item.priority_score, level: item.priority_level },
        status: item.status,
        description: item.description,
        assigned_technician_id: item.assigned_technician_id,
        ai_prediction: item.ai_prediction,
      })));
      setCompletedRepairs(completedRepairsData.repairs || []);
      setTechnicians((previous) => JSON.stringify(previous) === JSON.stringify(techniciansData.technicians || []) ? previous : (techniciansData.technicians || []));
      setConnected(true);
      setError("");
      setLastUpdated(new Date());
    } catch (err) {
      setConnected(false);
      setError(err?.message || "Cannot reach the CivicPriorityAI backend on port 8000.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (view !== "admin") return undefined;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loadAll starts an API request and owns loading state.
    loadAll(false);
    const interval = setInterval(() => loadAll(true), 10000);
    return () => clearInterval(interval);
  }, [view, loadAll]);

  useEffect(() => {
    if (view !== "admin" || loading) return undefined;
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) setActiveSection(visible.target.id);
    }, { rootMargin: "-25% 0px -60% 0px", threshold: [0.1, 0.35, 0.6] });
    Object.values(sectionRefs.current).forEach((node) => node && observer.observe(node));
    return () => observer.disconnect();
  }, [view, loading]);

  async function handleAssign(complaintId, technicianId) {
    try { await apiAssignTechnician(complaintId, technicianId); await loadAll(true); }
    catch (err) { setError(err.message || "Failed to assign technician."); }
  }

  async function handleStatusChange(complaintId, status) {
    try { await apiUpdateStatus(complaintId, status); await loadAll(true); }
    catch (err) { setError(err.message || "Failed to update status."); }
  }

  async function handleDeleteComplaint(complaintId) {
    await apiDeleteComplaint(complaintId);
    setSelectedId(null);
    await loadAll(true);
  }

  const visibleComplaints = useMemo(() => complaints.filter((complaint) => {
    const text = `${complaint.id} ${complaint.road?.name || ""} ${complaint.damage?.type || ""} ${complaint.description || ""}`.toLowerCase();
    return (!search || text.includes(search.toLowerCase()))
      && (statusFilter === "ALL" || complaint.status === statusFilter)
      && (priorityFilter === "ALL" || complaint.priority?.level === priorityFilter);
  }), [complaints, search, statusFilter, priorityFilter]);
  const visibleActiveComplaints = useMemo(() => activePriorityItems.filter((complaint) => {
    const text = `${complaint.id} ${complaint.road?.name || ""} ${complaint.damage?.type || ""} ${complaint.description || ""}`.toLowerCase();
    return (!search || text.includes(search.toLowerCase()))
      && (statusFilter === "ALL" || complaint.status === statusFilter)
      && (priorityFilter === "ALL" || complaint.priority?.level === priorityFilter);
  }), [activePriorityItems, search, statusFilter, priorityFilter]);

  if (view === "roles") return <RoleSelection onSelect={selectRole} />;
  if (view === "citizen") return <CitizenDashboard onBack={switchRole} />;
  if (view === "technician") return <TechnicianDashboard onBack={switchRole} />;
  if (loading) return <div className="loading-screen"><div className="loader" /><p>Loading CivicPriority AI admin workspace…</p></div>;

  const byStatus = dashboard?.by_status || {};
  const byPriority = dashboard?.by_priority || {};
  const activeByStatus = dashboard?.active_by_status || {};
  const pending = (activeByStatus.OPEN || 0) + (activeByStatus.PENDING || 0);
  const inProgress = (activeByStatus.ASSIGNED || 0) + (activeByStatus.IN_PROGRESS || 0);
  const resolved = (byStatus.REPAIRED || 0) + (byStatus.VERIFIED || 0) + (byStatus.RESOLVED || 0);
  const highPriority = (byPriority.HIGH || 0) + (byPriority.CRITICAL || 0);
  const selectedComplaint = complaints.find((complaint) => complaint.id === selectedId);
  const totalTechnicians = technicians.length;

  return <div className="app admin-app">
    <Sidebar activeSection={activeSection} onNavigate={(id) => { setActiveSection(id); sectionRefs.current[id]?.scrollIntoView({ behavior: "smooth", block: "start" }); }} connected={connected} onSwitchRole={switchRole} />
    <div className="main-column">
      <TopBar connected={connected} lastUpdated={lastUpdated} refreshing={refreshing} onRefresh={() => loadAll(true)} />
      <main className="content admin-content">
        {!connected && <div className="error-banner strong"><AlertTriangle size={16} />API connection lost — retrying.</div>}
        {error && connected && <div className="error-banner">{error}</div>}
        <header className="admin-page-header">
          <div><span className="hero-eyebrow">Civic road operations · Vellore</span><h1>CivicPriority AI</h1><p>Prioritize repairs, coordinate field teams, and track public infrastructure work.</p></div>
          <div className="admin-role-actions"><span className="admin-role-pill"><ShieldCheck size={15} />Admin workspace</span><button className="role-switch-btn" onClick={switchRole}><ArrowLeft size={15} />Switch role</button></div>
        </header>

        <section id="overview" ref={(node) => { sectionRefs.current.overview = node; }} className="admin-section">
          <SectionHeading eyebrow="At a glance" title="Overview" description="Current workload and service status." />
          <div className="stats-row admin-kpis">
            <StatCard label="Total complaints" value={dashboard?.summary?.total_complaints ?? complaints.length} icon={ClipboardList} tone="neutral" />
            <StatCard label="Pending" value={pending} icon={Clock3} tone="medium" />
            <StatCard label="In progress" value={inProgress} icon={Radar} tone="signal" />
            <StatCard label="Resolved" value={resolved} icon={ClipboardList} tone="success" />
            <StatCard label="High priority" value={highPriority} icon={AlertTriangle} tone="high" />
            <StatCard label="Technicians" value={totalTechnicians} icon={Users} tone="neutral" />
          </div>
          <div className="admin-overview-strip"><span>{dashboard?.data_note || "Live complaint records"}</span><span>{selectedComplaint ? `Selected complaint #${selectedComplaint.id}` : "Select any row to inspect evidence"}</span></div>
        </section>

        <section id="priority-queue" ref={(node) => { sectionRefs.current["priority-queue"] = node; }} className="admin-section">
          <SectionHeading eyebrow="Repair planning" title="Priority Repair Queue" description="Highest current priority first, with assignment and detail actions." />
          <PriorityQueue complaints={visibleActiveComplaints} selectedId={selectedId} onSelect={setSelectedId} technicians={technicians} onAssign={handleAssign} />
        </section>

        <section id="road-issues" ref={(node) => { sectionRefs.current["road-issues"] = node; }} className="admin-section">
          <SectionHeading eyebrow="Records" title="Complaint Management" description="Search and filter all complaints, then open the evidence drawer." />
          <div className="admin-filter-bar"><input aria-label="Search complaints" placeholder="Search ID, road, or damage…" value={search} onChange={(event) => setSearch(event.target.value)} /><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filter by status"><option value="ALL">All statuses</option>{[...new Set(complaints.map((item) => item.status).filter(Boolean))].sort().map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}</select><select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)} aria-label="Filter by priority"><option value="ALL">All priority levels</option>{[...new Set(complaints.map((item) => item.priority?.level).filter(Boolean))].sort().map((level) => <option key={level} value={level}>{level}</option>)}</select><span>{visibleComplaints.length} records</span></div>
          <PriorityQueue title="Complaint records" complaints={visibleComplaints} selectedId={selectedId} onSelect={setSelectedId} technicians={technicians} onAssign={handleAssign} />
        </section>

        <section id="technicians" ref={(node) => { sectionRefs.current.technicians = node; }} className="admin-section">
          <SectionHeading eyebrow="Field team" title="Technician Management" description="Workload and completion counts for active technicians." />
          <TechnicianPanel technicians={technicians} complaints={complaints} />
        </section>

        <section id="repairs" ref={(node) => { sectionRefs.current.repairs = node; }} className="admin-section">
          <SectionHeading eyebrow="Repair workflow" title="Repair Status" description="Complaint progress through the current service workflow." />
          <RepairPipeline byStatus={byStatus} />
        </section>

        <section id="completed-repairs" ref={(node) => { sectionRefs.current["completed-repairs"] = node; }} className="admin-section">
          <SectionHeading eyebrow="History" title="Completed Repairs" description="Repaired complaints remain available as historical records." />
          <CompletedRepairs repairs={completedRepairs} onSelect={setSelectedId} />
        </section>

        <section id="budget" ref={(node) => { sectionRefs.current.budget = node; }} className="admin-section">
          <SectionHeading eyebrow="Budget allocation" title="Repair Budget Optimizer" description="Existing budget-constrained repair recommendations." />
          <BudgetOptimizerPanel technicians={technicians} onAssigned={() => loadAll(true)} />
        </section>

        <section id="map" ref={(node) => { sectionRefs.current.map = node; }} className="admin-section">
          <SectionHeading eyebrow="Geographic view" title="Complaint Map" description="Vellore map with selectable complaint locations." />
          <MapPanel complaints={visibleActiveComplaints} selectedId={selectedId} onSelect={setSelectedId} />
        </section>

        <section id="analytics" ref={(node) => { sectionRefs.current.analytics = node; }} className="admin-section">
          <SectionHeading eyebrow="Trends" title="Analytics" description="Summary of current complaints and outcomes." />
          <div className="command-grid secondary"><AnalyticsPanel dashboard={dashboard} complaints={complaints} /><ActivityFeed complaints={complaints} /></div>
        </section>
        <footer className="app-footer"><span>CivicPriority AI · Vellore civic infrastructure</span><span>{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : ""}</span></footer>
      </main>
    </div>
    {selectedId != null && <div className="admin-detail-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedId(null); }}><aside className="admin-detail-drawer" aria-label={`Complaint ${selectedId} detail`}><button className="admin-drawer-close" onClick={() => setSelectedId(null)} aria-label="Close complaint detail"><X size={17} /></button><ComplaintDetail complaintId={selectedId} technicians={technicians} onClose={() => setSelectedId(null)} onAssign={handleAssign} onStatusChange={handleStatusChange} onWorkflowUpdate={() => loadAll(true)} onDelete={handleDeleteComplaint} /></aside></div>}
  </div>;
}

function SectionHeading({ eyebrow, title, description }) {
  return <div className="admin-section-heading"><div><span>{eyebrow}</span><h2>{title}</h2><p>{description}</p></div></div>;
}

function sameComplaints(a, b) {
  if (a.length !== b.length) return false;
  return a.every((item, index) => {
    const next = b[index];
    return item.id === next.id && item.status === next.status
      && item.priority?.score === next.priority?.score && item.priority?.level === next.priority?.level
      && item.road?.name === next.road?.name && item.road?.type === next.road?.type
      && item.damage?.type === next.damage?.type && item.damage?.severity === next.damage?.severity
      && item.assigned_technician_id === next.assigned_technician_id
      && item.location?.latitude === next.location?.latitude && item.location?.longitude === next.location?.longitude
      && item.created_at === next.created_at && item.updated_at === next.updated_at
      && JSON.stringify(item.activity || []) === JSON.stringify(next.activity || [])
      && item.ai_prediction?.model_status === next.ai_prediction?.model_status
      && item.ai_prediction?.predicted_priority_score === next.ai_prediction?.predicted_priority_score
      && item.ai_prediction?.model_version === next.ai_prediction?.model_version;
  });
}

export default App;
