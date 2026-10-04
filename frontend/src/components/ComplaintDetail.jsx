import { useEffect, useState } from "react";
import { Trash2, X } from "lucide-react";
import { getComplaint, getComplaintOutcomes, verifyRepair, API_BASE, complaintImageUrl } from "../api.js";
import { PriorityBadge } from "./StatusBadge.jsx";
import { damageSeverityLabel, detectionStateLabel, roadDamageLabel, yoloConfidenceLabel } from "../utils/complaintLabels.js";

const ASSIGNABLE_STATUSES = [
  "OPEN",
  "ASSIGNED",
  "IN_PROGRESS",
  "REPAIRED",
  "VERIFIED",
  "REJECTED",
];

// `Complaint.image_path` is stored as a filesystem path relative to
// the project root (e.g. "data/uploads/<name>.jpg", written by
// backend/app/api/complaints.py). backend/app/main.py mounts that
// same uploads directory at /uploads, so the browser-accessible URL
// is API_BASE + "/uploads/<filename>" — we only need the filename,
// which also makes this safe regardless of "/" vs "\" path
// separators. Absolute http(s) URLs, if ever stored, pass through
// unchanged.
function resolveImageUrl(imagePath) {
  if (!imagePath) return null;
  if (/^https?:\/\//i.test(imagePath)) return imagePath;

  const filename = imagePath.replace(/\\/g, "/").split("/").pop();
  if (!filename) return null;

  return `${API_BASE}/uploads/${filename}`;
}

export function ComplaintDetail({
  complaintId,
  technicians,
  onClose,
  onAssign,
  onStatusChange,
  onWorkflowUpdate,
  onDelete,
}) {
  const [detail, setDetail] = useState(null);
  const [workflow, setWorkflow] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [workflowError, setWorkflowError] = useState("");
  const [verificationNotes, setVerificationNotes] = useState("");
  const [verificationBusy, setVerificationBusy] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");

  async function handleDelete() {
    if (!onDelete) return;
    if (deleteConfirmation !== "DELETE") return;
    setDeleteBusy(true);
    setDeleteError("");
    try {
      await onDelete(complaintId);
      setDeleteDialogOpen(false);
      setDeleteConfirmation("");
    } catch (err) {
      setDeleteError(err.message || "Complaint could not be deleted.");
    } finally {
      setDeleteBusy(false);
    }
  }

  useEffect(() => {
    if (!complaintId) return;

    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- clear prior complaint evidence before fetching the newly selected record.
    setDetail(null);
    setWorkflow(null);
    setLoading(true);
    setError("");
    setWorkflowError("");
    setVerificationNotes("");

    getComplaint(complaintId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load complaint detail.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    getComplaintOutcomes(complaintId)
      .then((data) => { if (!cancelled) setWorkflow(data); })
      .catch((err) => { if (!cancelled) setWorkflowError(err.message || "Could not load repair records."); });

    return () => {
      cancelled = true;
    };
  }, [complaintId]);

  async function handleVerification(repairId, approved) {
    setVerificationBusy(true);
    setWorkflowError("");
    try {
      const result = await verifyRepair(repairId, approved, verificationNotes);
      setDetail((current) => current ? { ...current, status: result.complaint_status } : current);
      setWorkflow(await getComplaintOutcomes(complaintId));
      setVerificationNotes("");
      onWorkflowUpdate?.();
    } catch (err) {
      setWorkflowError(err.message || "Could not record repair verification.");
    } finally {
      setVerificationBusy(false);
    }
  }

  if (!complaintId) {
    return (
      <div className="detail-panel empty">
        <p>Select a road issue from the map or priority queue.</p>
      </div>
    );
  }

  const assignedTechnician = technicians.find(
    (t) => t.id === detail?.assigned_technician_id
  );

  const evidenceImageUrl = complaintImageUrl(detail?.annotated_image_path || detail?.image_path);
  const originalImageUrl = complaintImageUrl(detail?.image_path) || resolveImageUrl(detail?.image_path);

  return (
    <div className="detail-panel">
      <div className="detail-header">
        <div>
          <span className="detail-eyebrow">Incident record</span>
          <h2>Complaint #{String(complaintId).padStart(3, "0")}</h2>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close detail">
          <X size={16} />
        </button>
      </div>

      {loading && <div className="detail-loading">Loading record…</div>}
      {error && <div className="error-banner">{error}</div>}
      {deleteError && <div className="error-banner">{deleteError}</div>}
      {detail && onDelete && <button type="button" className="admin-view-btn danger" disabled={deleteBusy} onClick={() => { setDeleteConfirmation(""); setDeleteError(""); setDeleteDialogOpen(true); }}><Trash2 size={14} />Delete complaint</button>}
      {detail && onDelete && deleteDialogOpen && (
        <div className="delete-confirmation" role="dialog" aria-modal="true" aria-labelledby="delete-confirmation-title">
          <div className="delete-confirmation-card">
            <h3 id="delete-confirmation-title">Delete complaint permanently?</h3>
            <p>Complaint #{complaintId} and its associated uploaded or annotated images may be permanently deleted.</p>
            <label htmlFor="delete-confirmation-input">Type <strong>DELETE</strong> to confirm.</label>
            <input
              id="delete-confirmation-input"
              value={deleteConfirmation}
              onChange={(event) => setDeleteConfirmation(event.target.value)}
              autoComplete="off"
              autoFocus
            />
            <div className="delete-confirmation-actions">
              <button type="button" className="admin-view-btn" onClick={() => { setDeleteDialogOpen(false); setDeleteConfirmation(""); }}>Cancel</button>
              <button type="button" className="admin-view-btn danger" disabled={deleteConfirmation !== "DELETE" || deleteBusy} onClick={handleDelete}>
                {deleteBusy ? "Deleting…" : "Delete permanently"}
              </button>
            </div>
          </div>
        </div>
      )}

      {detail && !loading && (
        <div className="detail-body">
          <div
            style={{
              border: "1px solid var(--line)",
              borderRadius: "var(--radius-sm)",
              padding: "10px 12px",
              marginBottom: "4px",
              background: "var(--bg-base)",
            }}
          >
            <span
              style={{
                fontSize: "11px",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                color: "var(--text-tertiary)",
              }}
            >
              AI Analysis Image
            </span>

            {evidenceImageUrl ? (
              <a
                href={originalImageUrl || evidenceImageUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                <img
                  key={`${detail.id}-${evidenceImageUrl}`}
                  src={evidenceImageUrl}
                  alt={detail.annotated_image_path ? "YOLO annotated road-damage detections" : "Original citizen evidence; no reliable AI detection"}
                  style={{
                    display: "block",
                    marginTop: "8px",
                    width: "100%",
                    maxHeight: "220px",
                    objectFit: "contain",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--line)",
                    background: "var(--bg-void)",
                    cursor: "pointer",
                  }}
                />
              </a>
            ) : (
              <div
                className="empty-state"
                style={{ marginTop: "6px", padding: "10px 0" }}
              >
                No image uploaded
              </div>
            )}
            {!detail.annotated_image_path && detail.image_path && <p className="citizen-detection-note">{detail.damage?.type === "unknown" ? "No reliable AI detection is available; showing the original upload." : "No saved AI-annotated image is available for this report; showing the original upload."}</p>}
          </div>

          <div
            style={{
              border: "1px solid var(--line)",
              borderRadius: "var(--radius-sm)",
              padding: "10px 12px",
              marginBottom: "4px",
              background: "var(--bg-base)",
            }}
          >
            <span
              style={{
                fontSize: "11px",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                color: "var(--text-tertiary)",
              }}
            >
              Damage evidence and overall priority
            </span>

            <div className="detail-row">
              <span>Overall priority level</span>
              <PriorityBadge level={detail.priority?.level} />
            </div>

            <div className="detail-row">
              <span>Overall priority score</span>
              <strong className="mono">
                {detail.priority?.score ?? "Not available"}
              </strong>
            </div>

            <div className="detail-row">
              <span>Road damage</span>
              <strong>{roadDamageLabel(detail.damage)}</strong>
            </div>

            <div className="detail-row">
              <span>AI detection status</span>
              <strong>{detectionStateLabel(detail.damage)}</strong>
            </div>

            <div className="detail-row">
              <span>Damage severity</span>
              <strong>{damageSeverityLabel(detail.damage)}</strong>
            </div>

            <div className="detail-row">
              <span>YOLO confidence</span>
              <strong>{yoloConfidenceLabel(detail.damage, 0)}</strong>
            </div>

            {detail.damage?.type === "unknown" && (
              <div className="citizen-detection-note">
                YOLO did not confirm a supported damage class. This is not proof
                that visible distress is absent; review the uploaded photo. Overall
                priority is scored separately from damage severity.
              </div>
            )}

            <div className="detail-row">
              <span>Road</span>
              <strong>
                {detail.road?.name
                  ? `${detail.road.name}${detail.road?.type ? ` (${detail.road.type})` : ""
                  }`
                  : "Not available"}
              </strong>
            </div>

            {detail.priority?.recommended_action && (
              <div className="detail-row">
                <span>Recommended action</span>
                <strong>{detail.priority.recommended_action}</strong>
              </div>
            )}
            {detail.priority?.recurrence_count != null && (
              <div className="detail-row"><span>Other unresolved matches</span><strong>{detail.priority.recurrence_count}</strong></div>
            )}
            {detail.priority?.components && (
              <div style={{ marginTop: 10 }}>
                <strong style={{ fontSize: 12 }}>Evidence breakdown</strong>
                {Object.entries(detail.priority.components).map(([key, value]) => (
                  <div className="detail-row" key={key}>
                    <span>{key.replaceAll("_", " ")}</span>
                    <strong>{value.value == null ? "Unavailable" : `${Number(value.value).toFixed(0)}/100 · ${Number(value.weighted_points).toFixed(1)} pts`}</strong>
                  </div>
                ))}
              </div>
            )}
            {detail.priority?.explanations?.length > 0 && (
              <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
                {detail.priority.explanations.map((reason, index) => <li key={index}>{reason}</li>)}
              </ul>
            )}
          </div>

          <section className="panel repair-outcome-panel">
            <div className="panel-header"><div><h3>Repair and verification record</h3><p>Completion and verification details from the existing workflow.</p></div></div>
            {workflowError && <div className="error-banner">{workflowError}</div>}
            {workflow?.repairs?.length ? workflow.repairs.map((repair) => <div className="repair-record" key={repair.id}>
              <div className="detail-row"><span>Repair record</span><strong>#{repair.id} · {repair.verification_status}</strong></div>
              <div className="detail-row"><span>Completed</span><strong>{repair.completed_at ? new Date(repair.completed_at).toLocaleString() : "Unavailable"}</strong></div>
              <div className="detail-row"><span>Recorded cost</span><strong>{repair.repair_cost == null ? "Unavailable" : `₹${Number(repair.repair_cost).toLocaleString("en-IN")}`}</strong></div>
              {repair.repair_notes && <p>{repair.repair_notes}</p>}
              {repair.verification_status === "PENDING" && <div className="verification-controls">
                <label className="citizen-field"><span>Verification notes</span><textarea rows={2} value={verificationNotes} onChange={(event) => setVerificationNotes(event.target.value)} placeholder="Record inspection findings" /></label>
                <div><button type="button" className="admin-view-btn" disabled={verificationBusy} onClick={() => handleVerification(repair.id, true)}>Verify repair</button><button type="button" className="admin-view-btn" disabled={verificationBusy} onClick={() => handleVerification(repair.id, false)}>Request rework</button></div>
              </div>}
            </div>) : <p className="empty-state">{detail.status === "REPAIRED" ? "Repair is marked complete; the technician has not submitted its completion record yet." : "No repair completion record is available."}</p>}
            {workflow?.outcomes?.length > 0 && <div className="repair-outcome-history"><strong>Recorded outcomes</strong>{workflow.outcomes.map((outcome) => <div className="detail-row" key={outcome.id}><span>{outcome.result} · {outcome.created_at ? new Date(outcome.created_at).toLocaleString() : "Date unavailable"}</span><strong>{outcome.notes || "No notes"}</strong></div>)}</div>}
          </section>

          <section className="panel" style={{ padding: "12px", border: "1px solid var(--line)" }}>
            <span className="detail-eyebrow">AI priority prediction</span>
            {detail.ai_prediction?.model_status === "available" ? <>
              <div className="detail-row"><span>Rule-based overall priority</span><strong>{detail.ai_prediction.baseline_priority_score} · {detail.ai_prediction.baseline_priority_level}</strong></div>
              <div className="detail-row"><span>AI predicted overall priority</span><strong>{detail.ai_prediction.predicted_priority_score} · {detail.ai_prediction.predicted_priority_level}</strong></div>
              <div className="detail-row"><span>Difference from baseline</span><strong>{detail.ai_prediction.difference > 0 ? "+" : ""}{detail.ai_prediction.difference}</strong></div>
              <small>Model {detail.ai_prediction.model_version} · {detail.ai_prediction.model_status === "available" ? "Available" : "Unavailable"}</small>
              <p style={{ fontSize: 12 }}>{detail.ai_prediction.explanation}</p>
              <p style={{ fontSize: 12 }}>Per-complaint model contributions are unavailable; baseline evidence is shown separately above.</p>
            </> : <><strong>AI Prediction · Unavailable</strong><p style={{ fontSize: 12 }}>Reason: {detail.ai_prediction?.reason || "Model unavailable or inference failed."}</p><p style={{ fontSize: 12 }}>The rule-based baseline remains available above.</p></>}
          </section>

          <div className="detail-row">
            <span>Location</span>
            <strong className="mono">
              {detail.location?.latitude?.toFixed(5)},{" "}
              {detail.location?.longitude?.toFixed(5)}
            </strong>
          </div>

          <div className="detail-row">
            <span>Status</span>
            <select
              value={detail.status || ""}
              onChange={(e) => onStatusChange(complaintId, e.target.value)}
            >
              {ASSIGNABLE_STATUSES.filter((s) => s !== "VERIFIED" || detail.status === "VERIFIED").map((s) => (
                <option key={s} value={s}>
                  {s.replace("_", " ")}
                </option>
              ))}
            </select>
          </div>

          <div className="detail-row">
            <span>Assigned technician</span>
            {assignedTechnician ? (
              <strong>{assignedTechnician.name}</strong>
            ) : (
              <select
                defaultValue=""
                onChange={(e) =>
                  e.target.value && onAssign(complaintId, e.target.value)
                }
              >
                <option value="">Assign technician…</option>
                {technicians.map((tech) => (
                  <option key={tech.id} value={tech.id}>
                    {tech.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="detail-row">
            <span>Created</span>
            <strong>
              {detail.created_at
                ? new Date(detail.created_at).toLocaleString()
                : "Unknown"}
            </strong>
          </div>

          {detail.description && (
            <div className="detail-note">
              <span>Description</span>
              <p>{detail.description}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
