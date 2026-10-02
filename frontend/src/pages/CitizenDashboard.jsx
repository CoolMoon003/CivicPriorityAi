import { useCallback, useEffect, useState } from "react";
import { Activity, ArrowLeft, ClipboardList, FilePlus2, LogOut, MapPin, RefreshCw, UserRound } from "lucide-react";
import { complaintImageUrl as imageUrl, createCitizenProfile, getCitizenComplaint, getCitizenComplaints, getCitizenProfile, submitComplaint } from "../api.js";
import { PriorityBadge, StatusBadge } from "../components/StatusBadge.jsx";
import { damageSeverityLabel, detectionStateLabel, roadDamageLabel, yoloConfidenceLabel } from "../utils/complaintLabels.js";

const PROFILE_KEY = "civicpriority.citizenProfile";

function Metric({ label, value, tone = "" }) {
  return <div className={`citizen-metric ${tone}`}><span>{label}</span><strong>{value}</strong></div>;
}

export function CitizenDashboard({ onBack }) {
  const [profile, setProfile] = useState(null);
  const [profileForm, setProfileForm] = useState({ name: "", email: "", phone: "" });
  const [profileBusy, setProfileBusy] = useState(true);
  const [items, setItems] = useState([]);
  const [statuses, setStatuses] = useState({ pending: 0, in_progress: 0, resolved: 0, rejected: 0 });
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [form, setForm] = useState({ description: "", latitude: "", longitude: "" });
  const [image, setImage] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [result, setResult] = useState(null);

  const loadComplaints = useCallback(async (userId) => {
    setLoading(true);
    try {
      const data = await getCitizenComplaints(userId);
      setItems(data.items || []);
      setStatuses(data.statuses || { pending: 0, in_progress: 0, resolved: 0, rejected: 0 });
    } catch (err) {
      setError(err.message || "Could not load your complaints.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function restoreProfile() {
      let stored = null;
      try {
        stored = JSON.parse(localStorage.getItem(PROFILE_KEY) || "null");
      } catch {
        localStorage.removeItem(PROFILE_KEY);
      }
      try {
        if (stored?.id) {
          try {
            const current = await getCitizenProfile(stored.id);
            if (!cancelled) setProfile(current);
          } catch (err) {
            if (/Request failed \(404\)/.test(err.message || "")) {
              localStorage.removeItem(PROFILE_KEY);
            } else if (!cancelled) {
              setError(err.message || "Could not restore citizen profile.");
            }
          }
        }
      } finally {
        if (!cancelled) setProfileBusy(false);
      }
    }
    restoreProfile();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loadComplaints starts an API request and owns loading state.
    if (profile?.id) loadComplaints(profile.id);
  }, [profile?.id, loadComplaints]);

  useEffect(() => {
    if (!profile?.id || selectedId == null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- clear prior complaint data when no record is selected.
      setDetail(null);
      return;
    }
    let cancelled = false;
    getCitizenComplaint(profile.id, selectedId)
      .then((data) => { if (!cancelled) setDetail(data); })
      .catch((err) => { if (!cancelled) setError(err.message || "Could not load complaint detail."); });
    return () => { cancelled = true; };
  }, [profile?.id, selectedId]);

  async function handleProfileSubmit(event) {
    event.preventDefault();
    setError("");
    setProfileBusy(true);
    try {
      const current = await createCitizenProfile(profileForm);
      localStorage.setItem(PROFILE_KEY, JSON.stringify({ id: current.id }));
      setProfile(current);
    } catch (err) {
      setError(err.message || "Could not create citizen profile.");
    } finally {
      setProfileBusy(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!form.latitude || !form.longitude) {
      setError("Latitude and longitude are required.");
      return;
    }
    setSubmitting(true);
    setError("");
    setNotice("");
    setResult(null);
    try {
      const response = await submitComplaint({
        ...form, image, userId: profile.id,
      });
      setResult(response);
      setNotice(`Complaint #${response.complaint_id} submitted successfully.`);
      setImage(null);
      await loadComplaints(profile.id);
      setSelectedId(response.complaint_id);
      setActiveTab("report");
    } catch (err) {
      setError(err.message || "Complaint submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  function chooseTab(tab) {
    setActiveTab(tab);
    setError("");
    setNotice("");
    if (tab !== "complaints") setSelectedId(null);
  }

  function switchProfile() {
    localStorage.removeItem(PROFILE_KEY);
    setProfile(null);
    setItems([]);
    setSelectedId(null);
    setDetail(null);
    setActiveTab("dashboard");
    setResult(null);
  }

  if (profileBusy && !profile) {
    return <main className="citizen-page"><div className="citizen-shell"><p>Loading citizen profile…</p></div></main>;
  }

  if (!profile) {
    return (
      <main className="citizen-page">
        <div className="citizen-shell citizen-profile-shell">
          <button className="citizen-back" onClick={onBack} type="button"><ArrowLeft size={15} />Switch role</button>
          <div className="citizen-header"><span className="hero-eyebrow">CivicPriorityAI · Vellore</span><h1>Citizen dashboard</h1><p>Create a local citizen profile to associate your reports with this browser.</p></div>
          <form className="citizen-form panel" onSubmit={handleProfileSubmit}>
            <label className="citizen-field"><span>Name</span><input required value={profileForm.name} onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })} /></label>
            <label className="citizen-field"><span>Email</span><input required type="email" value={profileForm.email} onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })} /></label>
            <label className="citizen-field"><span>Phone (optional)</span><input value={profileForm.phone} onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })} /></label>
            <button className="citizen-submit" disabled={profileBusy}>{profileBusy ? "Saving profile…" : "Continue as citizen"}</button>
            <p className="citizen-identity-note">This project has no sign-in system yet. This profile is a browser-persisted demo identity, not an authenticated account.</p>
          </form>
          {error && <div className="error-banner strong citizen-alert">{error}</div>}
        </div>
      </main>
    );
  }


  return (
    <main className="citizen-page citizen-dashboard-page">
      <div className="citizen-dashboard-shell">
        <header className="citizen-dashboard-header">
          <div><span className="hero-eyebrow">CivicPriorityAI · Vellore</span><h1>Citizen dashboard</h1><p>Track road reports and follow their repair progress.</p></div>
          <div className="citizen-profile-chip"><UserRound size={16} /><span>{profile.name}</span><button type="button" onClick={switchProfile} title="Switch browser profile"><LogOut size={14} /></button></div>
        </header>

        <nav className="citizen-nav" aria-label="Citizen navigation">
          <button className={activeTab === "dashboard" ? "active" : ""} onClick={() => chooseTab("dashboard")}><Activity size={15} />Dashboard</button>
          <button className={activeTab === "report" ? "active" : ""} onClick={() => chooseTab("report")}><FilePlus2 size={15} />Report issue</button>
          <button className={activeTab === "complaints" ? "active" : ""} onClick={() => chooseTab("complaints")}><ClipboardList size={15} />My complaints <span>{items.length}</span></button>
          <button className="citizen-nav-back" onClick={onBack}><ArrowLeft size={15} />Admin</button>
        </nav>

        {error && <div className="error-banner strong citizen-alert">{error}</div>}
        {notice && <div className="citizen-notice">{notice}</div>}

        {activeTab === "dashboard" && (
          <section className="citizen-dashboard-content">
            <div className="citizen-metrics">
              <Metric label="Reports submitted" value={items.length} />
              <Metric label="Pending review" value={statuses.pending} tone="medium" />
              <Metric label="In progress" value={statuses.in_progress} tone="signal" />
              <Metric label="Resolved" value={statuses.resolved} tone="success" />
              <Metric label="Rejected" value={statuses.rejected} />
            </div>
            <div className="panel citizen-recent-panel">
              <div className="panel-header"><div><h2>Recent reports</h2><p>Your submitted road issues</p></div><button type="button" className="citizen-refresh" onClick={() => loadComplaints(profile.id)}><RefreshCw size={14} />Refresh</button></div>
              {items.length === 0 ? <p className="empty-state">No reports are linked to this profile yet.</p> : <div className="citizen-complaint-list">{items.slice(0, 4).map((item) => <ComplaintCard key={item.id} item={item} onSelect={(id) => { setSelectedId(id); setActiveTab("complaints"); }} />)}</div>}
            </div>
            <p className="citizen-identity-note">Contribution count reflects complaints linked to this profile. Older records without a citizen ID are not included.</p>
          </section>
        )}

        {activeTab === "report" && (
          <section className="citizen-report-layout">
            <div className="panel citizen-report-panel">
              <div className="panel-header"><div><h2>Report a road issue</h2><p>Photo, location, and description are sent to the existing complaint service.</p></div></div>
              <form className="citizen-form citizen-form-inner" onSubmit={handleSubmit}>
                <label className="citizen-field"><span>Description</span><textarea rows={3} placeholder="Describe the road issue" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
                <div className="citizen-field-row">
                  <label className="citizen-field"><span>Latitude</span><input required type="number" step="any" value={form.latitude} onChange={(e) => setForm({ ...form, latitude: e.target.value })} /></label>
                  <label className="citizen-field"><span>Longitude</span><input required type="number" step="any" value={form.longitude} onChange={(e) => setForm({ ...form, longitude: e.target.value })} /></label>
                </div>
                <button type="button" className="citizen-location-btn" onClick={() => {
                  if (!navigator.geolocation) { setError("Location is not supported by this browser."); return; }
                  navigator.geolocation.getCurrentPosition((position) => setForm((prev) => ({ ...prev, latitude: position.coords.latitude, longitude: position.coords.longitude })), () => setError("Location unavailable. Enter coordinates manually."));
                }}><MapPin size={14} />Use my location</button>
                <label className="citizen-field"><span>Road image (optional)</span><input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setImage(e.target.files?.[0] || null)} />{image && <small>{image.name} · {(image.size / 1024).toFixed(0)} KB</small>}</label>
                <button className="citizen-submit" type="submit" disabled={submitting}>{submitting ? "Uploading and analyzing…" : "Submit road issue"}</button>
              </form>
            </div>
            {result && <div className="panel citizen-result-panel"><h2>Complaint #{result.complaint_id} submitted</h2><div className="citizen-detection-result"><div><span>Road damage</span><strong>{roadDamageLabel(result.damage)}</strong></div><div><span>AI detection status</span><strong>{detectionStateLabel(result.damage)}</strong></div><div><span>Damage severity</span><strong>{damageSeverityLabel(result.damage)}</strong></div><div><span>YOLO confidence</span><strong>{yoloConfidenceLabel(result.damage)}</strong></div><div><span>Overall priority</span><strong>{result.priority?.score ?? "Unavailable"}</strong></div><div><span>Overall priority level</span><strong>{result.priority?.level ?? "Unavailable"}</strong></div><div><span>Status</span><strong>{result.status || "OPEN"}</strong></div></div>{result.damage?.description && <p className="citizen-detection-note">{result.damage.description}{result.damage?.detection_state === "possible" ? " This is uncertain AI evidence and is discounted in the damage part of the priority score; manual verification is recommended." : result.damage?.type === "unknown" ? " The detector did not find a reliable supported class. This is not proof that the visible road is undamaged; please have this photo reviewed. Overall priority is a separate score based on available road and location evidence." : " Damage severity is application policy based on the detected class; YOLO predicts the class, not severity."}</p>}{result.damage?.type === "unknown" && result.road?.type === "unclassified" && <p className="citizen-detection-note">The matched road is classified as unclassified in the road data, so local road and facility context is limited. This can lower overall priority independently of visible damage.</p>}<AIPredictionSummary prediction={result.ai_prediction} damage={result.damage} /><h3>AI Analysis Image</h3>{imageUrl(result.annotated_image_path || result.image_path) && <img className="citizen-result-image" src={imageUrl(result.annotated_image_path || result.image_path)} alt={result.annotated_image_path ? "YOLO annotated complaint image" : "Original complaint image"} />}{!result.annotated_image_path && result.image_path && <p className="citizen-detection-note">{result.annotation_error || (result.damage?.detection_state === "no_reliable_detection" ? "No reliable AI detection was available to annotate; showing the original upload." : "AI detections are available, but could not be annotated; showing the original upload.")}</p>}</div>}
          </section>
        )}

        {activeTab === "complaints" && (
          <section className="citizen-my-complaints">
            <div className="panel citizen-recent-panel"><div className="panel-header"><div><h2>My complaints</h2><p>Only reports linked to {profile.name}</p></div><button type="button" className="citizen-refresh" onClick={() => loadComplaints(profile.id)}><RefreshCw size={14} />Refresh</button></div>
              {loading ? <p className="empty-state">Loading your reports…</p> : items.length === 0 ? <p className="empty-state">No complaints found for this profile.</p> : <div className="citizen-complaint-list">{items.map((item) => <ComplaintCard key={item.id} item={item} selected={item.id === selectedId} onSelect={setSelectedId} />)}</div>}
            </div>
            <section className="panel citizen-detail-panel">
              {!selectedId ? <p className="empty-state">Select a report to view its details.</p> : !detail ? <p className="empty-state">Loading complaint details…</p> : <CitizenComplaintDetail detail={detail} />}
            </section>
          </section>
        )}
      </div>
    </main>
  );
}

function ComplaintCard({ item, onSelect, selected = false }) {
  const src = imageUrl(item.annotated_image_path || item.image_path);
  return <button type="button" className={`citizen-complaint-card ${selected ? "selected" : ""}`} onClick={() => onSelect(item.id)}>
    {src ? <img src={src} alt="Complaint evidence" /> : <div className="citizen-thumb-placeholder">No image</div>}
    <div className="citizen-card-main"><div className="citizen-card-title"><strong>Complaint #{item.id}</strong><StatusBadge status={item.status} /></div><span>Road damage: {roadDamageLabel(item.damage)} · Damage severity: {damageSeverityLabel(item.damage)}</span><small>{item.created_at ? new Date(item.created_at).toLocaleString() : "Date unavailable"}</small></div>
    <div className="citizen-card-priority"><PriorityBadge level={item.priority?.level} /><strong>{item.priority?.score ?? "—"}</strong></div>
  </button>;
}

function CitizenComplaintDetail({ detail }) {
  const src = imageUrl(detail.annotated_image_path || detail.image_path);
  return <div className="citizen-detail-content">
    <div className="panel-header"><div><span className="detail-eyebrow">My report</span><h2>Complaint #{detail.id}</h2></div><StatusBadge status={detail.status} /></div>
    <h3>AI Analysis Image</h3>{src ? <img className="citizen-detail-image" src={src} alt={`${detail.annotated_image_path ? "YOLO annotated analysis" : "Original evidence"} for complaint ${detail.id}`} /> : <p className="empty-state">No image was attached to this complaint.</p>}{!detail.annotated_image_path && detail.image_path && <p className="citizen-detection-note">{detail.damage?.type === "unknown" ? "No reliable AI detection is available; the original upload is shown." : "No saved AI-annotated image is available for this report; the original upload is shown."}</p>}
    <div className="citizen-detail-grid">
      <DetailValue label="Road damage" value={roadDamageLabel(detail.damage)} /><DetailValue label="AI detection status" value={detectionStateLabel(detail.damage)} /><DetailValue label="Damage severity" value={damageSeverityLabel(detail.damage)} />
      <DetailValue label="YOLO confidence" value={yoloConfidenceLabel(detail.damage)} />
      <DetailValue label="Overall priority score" value={detail.priority?.score} /><DetailValue label="Overall priority level" value={detail.priority?.level} />
      <DetailValue label="Road" value={detail.road?.name || detail.road?.type} />
      <DetailValue label="Location" value={detail.location ? `${detail.location.latitude}, ${detail.location.longitude}` : null} />
      <DetailValue label="Technician" value={detail.assigned_technician?.name || (detail.assigned_technician ? `#${detail.assigned_technician.id}` : null)} />
      <DetailValue label="Submitted" value={detail.created_at ? new Date(detail.created_at).toLocaleString() : null} />
    </div>
    {detail.description && <div className="detail-note"><span>Description</span><p>{detail.description}</p></div>}
    <AIPredictionSummary prediction={detail.ai_prediction} damage={detail.damage} />
    {detail.priority?.components && <div className="citizen-evidence"><h3>Priority evidence</h3>{Object.entries(detail.priority.components).map(([key, component]) => <div className="detail-row" key={key}><span>{key.replaceAll("_", " ")}</span><strong>{component.value == null ? "Unavailable" : `${Number(component.value).toFixed(0)}/100 · ${Number(component.weighted_points).toFixed(1)} pts`}</strong></div>)}</div>}
    {detail.priority?.explanations?.length > 0 && <ul className="citizen-explanations">{detail.priority.explanations.map((reason, i) => <li key={i}>{reason}</li>)}</ul>}
    <div className="citizen-timeline"><h3>Status timeline</h3>{detail.timeline?.length ? detail.timeline.map((entry, i) => <div className="citizen-timeline-entry" key={`${entry.created_at}-${i}`}><span className="citizen-timeline-dot" /><div><strong>{entry.event}</strong><small>{entry.created_at ? new Date(entry.created_at).toLocaleString() : "Date unavailable"}</small>{entry.notes && <p>{entry.notes}</p>}</div></div>) : <p className="empty-state">No additional status history is available.</p>}</div>
  </div>;
}

function AIPredictionSummary({ prediction, damage }) {
  return <section className="citizen-evidence"><h3>AI analysis</h3>{prediction?.model_status === "available" ? <>
    <DetailValue label="AI predicted overall priority" value={`${prediction.predicted_priority_score} · ${prediction.predicted_priority_level}`} />
    <DetailValue label="Rule-based overall priority" value={`${prediction.baseline_priority_score} · ${prediction.baseline_priority_level}`} />
    {damage?.type === "unknown" && <p>AI priority prediction uses available structured and contextual information. YOLO did not confirm a supported damage class; damage severity remains undetermined and the photo may need human review.</p>}
    <p>Per-complaint model contributions are unavailable; the AI score is separate from the rule-based evidence.</p>
  </> : <p>AI prediction unavailable. Rule-based priority remains available.</p>}</section>;
}

function DetailValue({ label, value }) {
  return <div className="citizen-detail-value"><span>{label}</span><strong>{value ?? "Unavailable"}</strong></div>;
}
