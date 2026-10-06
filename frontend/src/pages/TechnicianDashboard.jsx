import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, MapPin, RefreshCw, Wrench } from "lucide-react";
import {
  complaintImageUrl,
  complaintNavigationUrl,
  createRepairRecord,
  getTechnicians,
  getTechnicianComplaints,
  updateTechnicianComplaintStatus,
} from "../api.js";
import { PriorityBadge, StatusBadge } from "../components/StatusBadge.jsx";
import { damageSeverityLabel, detectionStateLabel, roadDamageLabel, yoloConfidenceLabel } from "../utils/complaintLabels.js";

const LANGUAGE_KEY = "civicpriority.technicianLanguage";
const translations = {
  en: {
    language: "English",
    tamil: "தமிழ்",
    eyebrow: "CivicPriority AI · Field operations",
    title: "Technician workspace",
    intro: "Review assigned road repair work and update progress.",
    switchRole: "Switch role",
    assignedRepairs: "Assigned repairs",
    loadedFrom: "Work orders are loaded from the technician service.",
    refresh: "Refresh",
    selectTechnician: "Select technician",
    loading: "Loading assigned repairs…",
    noTechnicians: "No active technicians are registered.",
    noComplaints: "No complaints are assigned to this technician.",
    complaint: "Complaint",
    road: "Road",
    priority: "Priority",
    status: "Status",
    location: "Location",
    update: "Update",
    viewDetails: "View details",
    unknownRoad: "Unknown road",
    locate: "Locate Spot",
    close: "Close",
    workDetails: "Work details",
    roadUnavailable: "Road name unavailable",
    noDescription: "No citizen description",
    roadDamage: "Road damage",
    aiAssessment: "AI assessment",
    severity: "Damage severity",
    confidence: "YOLO confidence",
    overallPriority: "Overall priority",
    analysisImage: "AI Analysis Image",
    noImage: "No image was uploaded for this complaint.",
    possibleDamage: "Possible damage detected by AI. Manual verification recommended before repair work is planned.",
    noReliableDetection: "No reliable AI detection is available; the original image is shown.",
    noAnnotatedImage: "No saved AI-annotated image is available for this report; the original image is shown.",
    startWork: "Start work",
    completeWork: "Complete work",
    assignedHelp: "This complaint is assigned to you.",
    inProgressHelp: "Repair work has started for this complaint.",
    repairedHelp: "Repair is marked complete; record the completed work below.",
    completedHelp: "The repair completion record has been saved.",
    recordRepair: "Record completed repair",
    repairedExplicitly: "The repair was explicitly marked REPAIRED. Enter actual details; leave unknown cost blank.",
    notes: "Repair notes",
    describeWork: "Describe completed work",
    cost: "Recorded repair cost (₹, optional)",
    unknownCost: "Leave blank if unknown",
    save: "Save completion record",
    saving: "Saving…",
    completionRecorded: "Completion recorded",
    unavailable: "Unavailable",
    verification: "Verification",
    costValue: "Cost",
    navigateError: "Complaint coordinates are unavailable or invalid.",
    loadTechniciansError: "Could not load technicians.",
    loadWorkError: "Could not load assigned work.",
    updateError: "Could not update repair status.",
    saveError: "Could not save repair details.",
    workflow: "Workflow",
  },
  ta: {
    language: "English",
    tamil: "தமிழ்",
    eyebrow: "CivicPriority AI · களப் பணிகள்",
    title: "தொழில்நுட்ப பணியாளர் பணித்தளம்",
    intro: "ஒதுக்கப்பட்ட சாலைப் பழுதுபார்ப்பு பணிகளைப் பார்த்து முன்னேற்றத்தைப் புதுப்பிக்கவும்.",
    switchRole: "பங்கை மாற்று",
    assignedRepairs: "ஒதுக்கப்பட்ட பழுதுபார்ப்புகள்",
    loadedFrom: "தொழில்நுட்ப பணியாளர் சேவையிலிருந்து பணிகள் ஏற்றப்படுகின்றன.",
    refresh: "புதுப்பி",
    selectTechnician: "தொழில்நுட்ப பணியாளரைத் தேர்வு செய்க",
    loading: "ஒதுக்கப்பட்ட பணிகள் ஏற்றப்படுகின்றன…",
    noTechnicians: "செயலில் உள்ள தொழில்நுட்ப பணியாளர்கள் இல்லை.",
    noComplaints: "இந்த தொழில்நுட்ப பணியாளருக்கு புகார்கள் ஒதுக்கப்படவில்லை.",
    complaint: "புகார்",
    road: "சாலை",
    priority: "முன்னுரிமை",
    status: "நிலை",
    location: "இடம்",
    update: "புதுப்பி",
    viewDetails: "விவரங்களைப் பார்",
    unknownRoad: "சாலை பெயர் இல்லை",
    locate: "இடத்திற்குச் செல்ல",
    close: "மூடு",
    workDetails: "பணி விவரங்கள்",
    roadUnavailable: "சாலை பெயர் கிடைக்கவில்லை",
    noDescription: "குடிமகன் விளக்கம் இல்லை",
    roadDamage: "சாலை சேதம்",
    aiAssessment: "AI மதிப்பீடு",
    severity: "சேதத்தின் தீவிரம்",
    confidence: "YOLO நம்பிக்கை",
    overallPriority: "மொத்த முன்னுரிமை",
    analysisImage: "AI ஆய்வு படம்",
    noImage: "இந்த புகாருக்கு படம் பதிவேற்றப்படவில்லை.",
    possibleDamage: "AI மூலம் சாத்தியமான சேதம் கண்டறியப்பட்டது. பழுதுபார்ப்புக்கு முன் நேரடி சரிபார்ப்பு பரிந்துரைக்கப்படுகிறது.",
    noReliableDetection: "நம்பகமான AI கண்டறிதல் இல்லை; அசல் படம் காட்டப்படுகிறது.",
    noAnnotatedImage: "இந்த அறிக்கைக்கு AI குறியீட்டுப் படம் இல்லை; அசல் படம் காட்டப்படுகிறது.",
    startWork: "பணியைத் தொடங்கு",
    completeWork: "பணியை முடி",
    assignedHelp: "இந்த புகார் உங்களுக்கு ஒதுக்கப்பட்டுள்ளது.",
    inProgressHelp: "இந்த சாலைப் பழுதை சரிசெய்யும் பணி தொடங்கப்பட்டுள்ளது.",
    repairedHelp: "பழுது சரிசெய்யப்பட்டதாகக் குறிக்கப்பட்டுள்ளது; கீழே பணி விவரங்களைப் பதிவு செய்யவும்.",
    completedHelp: "பழுதுபார்ப்பு நிறைவு பதிவு சேமிக்கப்பட்டது.",
    recordRepair: "முடிக்கப்பட்ட பழுதுபார்ப்பைப் பதிவு செய்க",
    repairedExplicitly: "பழுது REPAIRED எனக் குறிக்கப்பட்டுள்ளது. உண்மையான விவரங்களை உள்ளிடவும்; செலவு தெரியாவிட்டால் காலியாக விடவும்.",
    notes: "பழுதுபார்ப்பு குறிப்புகள்",
    describeWork: "முடிக்கப்பட்ட பணியை விவரிக்கவும்",
    cost: "பதிவுசெய்யப்பட்ட செலவு (₹, விருப்பம்)",
    unknownCost: "தெரியாவிட்டால் காலியாக விடவும்",
    save: "நிறைவு பதிவைச் சேமி",
    saving: "சேமிக்கப்படுகிறது…",
    completionRecorded: "நிறைவு பதிவு செய்யப்பட்டது",
    unavailable: "கிடைக்கவில்லை",
    verification: "சரிபார்ப்பு",
    costValue: "செலவு",
    navigateError: "புகாரின் இடத்தகவல் இல்லை அல்லது தவறாக உள்ளது.",
    loadTechniciansError: "தொழில்நுட்ப பணியாளர்களை ஏற்ற முடியவில்லை.",
    loadWorkError: "ஒதுக்கப்பட்ட பணிகளை ஏற்ற முடியவில்லை.",
    updateError: "பழுதுபார்ப்பு நிலையைப் புதுப்பிக்க முடியவில்லை.",
    saveError: "பழுதுபார்ப்பு விவரங்களைச் சேமிக்க முடியவில்லை.",
    workflow: "பணி நிலைகள்",
  },
};

const workflowStatuses = ["ASSIGNED", "IN_PROGRESS", "REPAIRED"];
const statusLabel = (status, t) => ({
  ASSIGNED: t.assignedHelp,
  IN_PROGRESS: t.inProgressHelp,
  REPAIRED: t.repairedHelp,
}[status] || status);

export function TechnicianDashboard({ onBack }) {
  const [technicians, setTechnicians] = useState([]);
  const [technicianId, setTechnicianId] = useState("");
  const [work, setWork] = useState(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedComplaintId, setSelectedComplaintId] = useState(null);
  const [language, setLanguage] = useState(() => localStorage.getItem(LANGUAGE_KEY) || "en");
  const t = translations[language];

  function changeLanguage(nextLanguage) {
    setLanguage(nextLanguage);
    localStorage.setItem(LANGUAGE_KEY, nextLanguage);
  }

  useEffect(() => {
    getTechnicians().then((data) => {
      setTechnicians(data.technicians || []);
      if (data.technicians?.length) setTechnicianId(String(data.technicians[0].id));
    }).catch((err) => setError(err.message || t.loadTechniciansError)).finally(() => setLoading(false));
  }, [t.loadTechniciansError]);

  const loadWork = useCallback(async () => {
    if (!technicianId) return;
    setLoading(true);
    try { setWork(await getTechnicianComplaints(technicianId)); setError(""); }
    catch (err) { setError(err.message || t.loadWorkError); }
    finally { setLoading(false); }
  }, [technicianId, t.loadWorkError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loadWork starts an API request and owns loading state.
    loadWork();
  }, [loadWork]);

  async function updateStatus(complaintId, status) {
    setBusyId(complaintId);
    try { await updateTechnicianComplaintStatus(technicianId, complaintId, status); await loadWork(); }
    catch (err) { setError(err.message || t.updateError); }
    finally { setBusyId(null); }
  }

  function navigateToComplaint(item) {
    const url = complaintNavigationUrl(item.latitude, item.longitude);
    if (!url) {
      setError(t.navigateError);
      return;
    }
    window.open(url, "_blank", "noopener,noreferrer");
  }

  const repairedWithoutRecord = work?.complaints?.filter((item) =>
    item.status === "REPAIRED" && (!item.repair_record
      || item.repair_record.verification_status === "REJECTED")) || [];
  const selectedComplaint = work?.complaints?.find((item) => item.id === selectedComplaintId);

  return <main className="role-workspace-page"><div className="role-workspace-shell">
    <header className="role-workspace-header"><div><span className="hero-eyebrow">{t.eyebrow}</span><h1>{t.title}</h1><p>{t.intro}</p></div><div className="technician-header-actions"><div className="language-toggle" role="group" aria-label="Language"><button type="button" className={language === "en" ? "active" : ""} onClick={() => changeLanguage("en")}>{t.language}</button><button type="button" className={language === "ta" ? "active" : ""} onClick={() => changeLanguage("ta")}>{t.tamil}</button></div><button className="role-switch-btn" onClick={onBack}><ArrowLeft size={15} />{t.switchRole}</button></div></header>
    <section className="panel technician-work-panel"><div className="panel-header"><div><h2><Wrench size={15} /> {t.assignedRepairs}</h2><p>{t.loadedFrom}</p></div><div className="technician-work-controls"><select value={technicianId} onChange={(e) => setTechnicianId(e.target.value)} aria-label={t.selectTechnician}>{technicians.map((tech) => <option key={tech.id} value={tech.id}>{tech.name}</option>)}</select><button className="citizen-refresh" onClick={loadWork} type="button"><RefreshCw size={14} />{t.refresh}</button></div></div>
      {error && <div className="error-banner strong">{error}</div>}
      {loading ? <div className="empty-state">{t.loading}</div> : !technicians.length ? <div className="empty-state">{t.noTechnicians}</div> : !work?.complaints?.length ? <div className="empty-state">{t.noComplaints}</div> : <div className="table-wrapper"><table><thead><tr><th>{t.complaint}</th><th>{t.road}</th><th>{t.priority}</th><th>{t.status}</th><th>{t.location}</th><th>{t.update}</th></tr></thead><tbody>{work.complaints.map((item) => <tr key={item.id}><td><button type="button" className="text-button" onClick={() => setSelectedComplaintId(item.id)}>#{String(item.id).padStart(3, "0")} · {t.viewDetails}</button><button type="button" className="technician-navigate-btn" onClick={() => navigateToComplaint(item)}><MapPin size={13} />{t.locate}</button></td><td>{item.road_name || t.unknownRoad}</td><td><span className="technician-priority"><PriorityBadge level={item.priority} />{item.priority_score ?? "—"}</span></td><td><StatusBadge status={item.status} /><small className="technician-status-help">{statusLabel(item.status, t)}</small></td><td className="mono">{item.latitude?.toFixed?.(4)}, {item.longitude?.toFixed?.(4)}</td><td><select aria-label={`${t.update} ${t.complaint} ${item.id}`} disabled={busyId === item.id} value={item.status === "ASSIGNED" ? "" : item.status} onChange={(e) => e.target.value && updateStatus(item.id, e.target.value)}>{item.status === "ASSIGNED" && <option value="" disabled>{t.startWork}</option>}{["IN_PROGRESS", "REPAIRED"].map((status) => <option key={status} value={status}>{status === "IN_PROGRESS" ? t.startWork : t.completeWork}</option>)}</select></td></tr>)}</tbody></table></div>}
      {selectedComplaint && <TechnicianComplaintDetail item={selectedComplaint} t={t} onNavigate={() => navigateToComplaint(selectedComplaint)} onClose={() => setSelectedComplaintId(null)} />}
      {!loading && work?.complaints?.filter((item) => item.repair_record
        && item.repair_record.verification_status !== "REJECTED").map((item) => <RepairRecordSummary key={item.id} item={item} t={t} />)}
      {!loading && repairedWithoutRecord.map((item) => <RepairCompletionForm key={item.id} item={item} technicianId={technicianId} t={t} onSaved={loadWork} />)}
    </section>
    <p className="role-demo-note">Technician selection is for this demo workspace. The project does not currently authenticate technician sessions.</p>
  </div></main>;
}

function TechnicianComplaintDetail({ item, t, onNavigate, onClose }) {
  const src = complaintImageUrl(item.annotated_image_path || item.image_path);
  return <section className="panel technician-complaint-detail" aria-label={`${t.complaint} ${item.id} ${t.workDetails}`}>
    <div className="panel-header"><div><h3>{t.complaint} #{item.id} · {t.workDetails}</h3><p>{item.road_name || t.roadUnavailable} · {item.description || t.noDescription}</p></div><div className="technician-detail-actions"><button type="button" className="technician-navigate-btn" onClick={onNavigate}><MapPin size={13} />{t.locate}</button><button type="button" className="citizen-refresh" onClick={onClose}>{t.close}</button></div></div>
    <div className="technician-workflow"><span>{t.workflow}</span><div>{workflowStatuses.map((status) => <strong className={status === item.status ? "current" : ""} key={status}>{status === "ASSIGNED" ? "Assigned" : status === "IN_PROGRESS" ? "Work Started" : "Completed"}</strong>)}</div><p>{statusLabel(item.status, t)}</p></div>
    <div className="citizen-result-grid"><div><span>{t.roadDamage}</span><strong>{roadDamageLabel(item.damage)}</strong></div><div><span>{t.aiAssessment}</span><strong>{detectionStateLabel(item.damage)}</strong></div><div><span>{t.severity}</span><strong>{damageSeverityLabel(item.damage)}</strong></div><div><span>{t.confidence}</span><strong>{yoloConfidenceLabel(item.damage)}</strong></div><div><span>{t.overallPriority}</span><strong>{item.priority_score ?? "—"} · {item.priority || "Unknown"}</strong></div><div><span>{t.location}</span><strong>{item.latitude}, {item.longitude}</strong></div></div>
    {item.damage?.detection_state === "possible" && <p className="citizen-detection-note">{t.possibleDamage}</p>}
    <h4>{t.analysisImage}</h4>{src ? <a href={src} target="_blank" rel="noreferrer"><img className="technician-evidence-image" src={src} alt={`${item.annotated_image_path ? "YOLO annotated analysis" : "Original evidence"} for complaint ${item.id}`} /></a> : <p className="empty-state">{t.noImage}</p>}{!item.annotated_image_path && item.image_path && <p className="citizen-detection-note">{item.damage?.type === "unknown" ? t.noReliableDetection : t.noAnnotatedImage}</p>}
  </section>;
}

function RepairCompletionForm({ item, technicianId, t, onSaved }) {
  const [notes, setNotes] = useState("");
  const [cost, setCost] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try { await createRepairRecord(item.id, { technicianId, repairNotes: notes, repairCost: cost }); await onSaved(); }
    catch (err) { setError(err.message || t.saveError); }
    finally { setBusy(false); }
  }
  return <form className="panel repair-completion-form" onSubmit={submit}>
    <div className="panel-header"><div><h3>{t.recordRepair} · #{item.id}</h3><p>{t.repairedExplicitly}</p></div></div>
    <label className="citizen-field"><span>{t.notes}</span><textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder={t.describeWork} /></label>
    <label className="citizen-field"><span>{t.cost}</span><input type="number" min="0" step="0.01" value={cost} onChange={(event) => setCost(event.target.value)} placeholder={t.unknownCost} /></label>
    {error && <div className="error-banner">{error}</div>}
    <button type="submit" className="citizen-submit" disabled={busy}>{busy ? t.saving : t.save}</button>
  </form>;
}

function RepairRecordSummary({ item, t }) {
  const repair = item.repair_record;
  return <div className="repair-record-summary"><strong><CheckCircle2 size={14} /> {t.complaint} #{item.id} · {t.completionRecorded}</strong><span>{t.costValue}: {repair.repair_cost == null ? t.unavailable : `₹${Number(repair.repair_cost).toLocaleString("en-IN")}`}</span><span>{t.verification}: {repair.verification_status}</span>{repair.repair_notes && <p>{repair.repair_notes}</p>}</div>;
}
