import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, RefreshCw, Wrench } from "lucide-react";
import { complaintImageUrl, createRepairRecord, getTechnicians, getTechnicianComplaints, updateTechnicianComplaintStatus } from "../api.js";
import { PriorityBadge, StatusBadge } from "../components/StatusBadge.jsx";
import { damageSeverityLabel, detectionStateLabel, roadDamageLabel, yoloConfidenceLabel } from "../utils/complaintLabels.js";

export function TechnicianDashboard({ onBack }) {
  const [technicians, setTechnicians] = useState([]);
  const [technicianId, setTechnicianId] = useState("");
  const [work, setWork] = useState(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedComplaintId, setSelectedComplaintId] = useState(null);

  useEffect(() => {
    getTechnicians().then((data) => {
      setTechnicians(data.technicians || []);
      if (data.technicians?.length) setTechnicianId(String(data.technicians[0].id));
    }).catch((err) => setError(err.message || "Could not load technicians.")).finally(() => setLoading(false));
  }, []);

  const loadWork = useCallback(async () => {
    if (!technicianId) return;
    setLoading(true);
    try { setWork(await getTechnicianComplaints(technicianId)); setError(""); }
    catch (err) { setError(err.message || "Could not load assigned work."); }
    finally { setLoading(false); }
  }, [technicianId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loadWork starts an API request and owns loading state.
    loadWork();
  }, [loadWork]);

  async function updateStatus(complaintId, status) {
    setBusyId(complaintId);
    try { await updateTechnicianComplaintStatus(technicianId, complaintId, status); await loadWork(); }
    catch (err) { setError(err.message || "Could not update repair status."); }
    finally { setBusyId(null); }
  }

  const repairedWithoutRecord = work?.complaints?.filter((item) =>
    item.status === "REPAIRED" && (!item.repair_record
      || item.repair_record.verification_status === "REJECTED")) || [];
  const selectedComplaint = work?.complaints?.find((item) => item.id === selectedComplaintId);

  return <main className="role-workspace-page"><div className="role-workspace-shell">
    <header className="role-workspace-header"><div><span className="hero-eyebrow">CivicPriority AI · Field operations</span><h1>Technician workspace</h1><p>Review assigned road repair work and update progress.</p></div><button className="role-switch-btn" onClick={onBack}><ArrowLeft size={15} />Switch role</button></header>
    <section className="panel technician-work-panel"><div className="panel-header"><div><h2><Wrench size={15} /> Assigned repairs</h2><p>Work orders are loaded from the technician service.</p></div><div className="technician-work-controls"><select value={technicianId} onChange={(e) => setTechnicianId(e.target.value)} aria-label="Select technician">{technicians.map((tech) => <option key={tech.id} value={tech.id}>{tech.name}</option>)}</select><button className="citizen-refresh" onClick={loadWork} type="button"><RefreshCw size={14} />Refresh</button></div></div>
      {error && <div className="error-banner strong">{error}</div>}
      {loading ? <div className="empty-state">Loading assigned repairs…</div> : !technicians.length ? <div className="empty-state">No active technicians are registered.</div> : !work?.complaints?.length ? <div className="empty-state">No complaints are assigned to this technician.</div> : <div className="table-wrapper"><table><thead><tr><th>Complaint</th><th>Road</th><th>Priority</th><th>Status</th><th>Location</th><th>Update</th></tr></thead><tbody>{work.complaints.map((item) => <tr key={item.id}><td><button type="button" className="text-button" onClick={() => setSelectedComplaintId(item.id)}>#{String(item.id).padStart(3, "0")} · View details</button></td><td>{item.road_name || "Unknown road"}</td><td><span className="technician-priority"><PriorityBadge level={item.priority} />{item.priority_score ?? "—"}</span></td><td><StatusBadge status={item.status} /></td><td className="mono">{item.latitude?.toFixed?.(4)}, {item.longitude?.toFixed?.(4)}</td><td><select aria-label={`Update complaint ${item.id}`} disabled={busyId === item.id} value={item.status} onChange={(e) => updateStatus(item.id, e.target.value)}>{["ASSIGNED", "IN_PROGRESS", "REPAIRED"].map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}</select></td></tr>)}</tbody></table></div>}
      {selectedComplaint && <TechnicianComplaintDetail item={selectedComplaint} onClose={() => setSelectedComplaintId(null)} />}
      {!loading && work?.complaints?.filter((item) => item.repair_record
        && item.repair_record.verification_status !== "REJECTED").map((item) => <RepairRecordSummary key={item.id} item={item} />)}
      {!loading && repairedWithoutRecord.map((item) => <RepairCompletionForm key={item.id} item={item} technicianId={technicianId} onSaved={loadWork} />)}
    </section>
    <p className="role-demo-note">Technician selection is for this demo workspace. The project does not currently authenticate technician sessions.</p>
  </div></main>;
}

function TechnicianComplaintDetail({ item, onClose }) {
  const src = complaintImageUrl(item.annotated_image_path || item.image_path);
  return <section className="panel technician-complaint-detail" aria-label={`Complaint ${item.id} details`}>
    <div className="panel-header"><div><h3>Complaint #{item.id} · Work details</h3><p>{item.road_name || "Road name unavailable"} · {item.description || "No citizen description"}</p></div><button type="button" className="citizen-refresh" onClick={onClose}>Close</button></div>
    <div className="citizen-result-grid"><div><span>Road damage</span><strong>{roadDamageLabel(item.damage)}</strong></div><div><span>AI assessment</span><strong>{detectionStateLabel(item.damage)}</strong></div><div><span>Damage severity</span><strong>{damageSeverityLabel(item.damage)}</strong></div><div><span>YOLO confidence</span><strong>{yoloConfidenceLabel(item.damage)}</strong></div><div><span>Overall priority</span><strong>{item.priority_score ?? "—"} · {item.priority || "Unknown"}</strong></div><div><span>Location</span><strong>{item.latitude}, {item.longitude}</strong></div></div>
    {item.damage?.detection_state === "possible" && <p className="citizen-detection-note">Possible damage detected by AI. Manual verification recommended before repair work is planned.</p>}
    <h4>AI Analysis Image</h4>{src ? <a href={src} target="_blank" rel="noreferrer"><img className="technician-evidence-image" src={src} alt={`${item.annotated_image_path ? "YOLO annotated analysis" : "Original evidence"} for complaint ${item.id}`} /></a> : <p className="empty-state">No image was uploaded for this complaint.</p>}{!item.annotated_image_path && item.image_path && <p className="citizen-detection-note">{item.damage?.type === "unknown" ? "No reliable AI detection is available; the original image is shown." : "No saved AI-annotated image is available for this report; the original image is shown."}</p>}
  </section>;
}

function RepairCompletionForm({ item, technicianId, onSaved }) {
  const [notes, setNotes] = useState("");
  const [cost, setCost] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await createRepairRecord(item.id, { technicianId, repairNotes: notes, repairCost: cost });
      await onSaved();
    } catch (err) { setError(err.message || "Could not save repair details."); }
    finally { setBusy(false); }
  }
  return <form className="panel repair-completion-form" onSubmit={submit}>
    <div className="panel-header"><div><h3>Record completed repair · #{item.id}</h3><p>The repair was explicitly marked REPAIRED. Enter actual details; leave unknown cost blank.</p></div></div>
    <label className="citizen-field"><span>Repair notes</span><textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Describe completed work" /></label>
    <label className="citizen-field"><span>Recorded repair cost (₹, optional)</span><input type="number" min="0" step="0.01" value={cost} onChange={(event) => setCost(event.target.value)} placeholder="Leave blank if unknown" /></label>
    {error && <div className="error-banner">{error}</div>}
    <button type="submit" className="citizen-submit" disabled={busy}>{busy ? "Saving…" : "Save completion record"}</button>
  </form>;
}

function RepairRecordSummary({ item }) {
  const repair = item.repair_record;
  return <div className="repair-record-summary"><strong>Complaint #{item.id} · Completion recorded</strong><span>Cost: {repair.repair_cost == null ? "Unavailable" : `₹${Number(repair.repair_cost).toLocaleString("en-IN")}`}</span><span>Verification: {repair.verification_status}</span>{repair.repair_notes && <p>{repair.repair_notes}</p>}</div>;
}
