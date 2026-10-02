import { useState } from "react";
import {
    AlertTriangle,
    ArrowLeft,
    CheckCircle2,
    LocateFixed,
    Upload,
} from "lucide-react";
import { submitComplaint, API_BASE, complaintImageUrl } from "../api.js";
import { damageSeverityLabel, detectionStateLabel, roadDamageLabel, yoloConfidenceLabel } from "../utils/complaintLabels.js";

const initialForm = {
    description: "",
    latitude: "",
    longitude: "",
};

export function CitizenComplaintPage({ onBack }) {
    const [form, setForm] = useState(initialForm);
    const [image, setImage] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [result, setResult] = useState(null);
    const [duplicateWarning, setDuplicateWarning] = useState(null);
    const [duplicateComplaintId, setDuplicateComplaintId] = useState(null);
    const [locating, setLocating] = useState(false);
    const [locationMessage, setLocationMessage] = useState("");
    const [locationError, setLocationError] = useState("");
    const [trackId, setTrackId] = useState("");
    const [tracking, setTracking] = useState(false);
    const [trackError, setTrackError] = useState("");
    const [trackResult, setTrackResult] = useState(null);

    function handleChange(field, value) {
        setForm((prev) => ({ ...prev, [field]: value }));
    }

    function handleUseLocation() {
        setLocationMessage("");
        setLocationError("");

        if (!navigator.geolocation) {
            setLocationError("Location is not supported by this browser.");
            return;
        }

        setLocating(true);
        navigator.geolocation.getCurrentPosition(
            (position) => {
                setForm((prev) => ({
                    ...prev,
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                }));
                setLocationMessage("Location detected.");
                setLocating(false);
            },
            (geoError) => {
                const message =
                    geoError.code === geoError.PERMISSION_DENIED
                        ? "Location permission denied. Enter coordinates manually."
                        : "Could not detect location. Enter coordinates manually.";
                setLocationError(message);
                setLocating(false);
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    }

    async function handleSubmit(e, continueAsSeparate = false) {
        e?.preventDefault?.();
        setError("");
        setResult(null);
        setDuplicateWarning(null);
        setDuplicateComplaintId(null);

        if (form.latitude === "" || form.longitude === "") {
            setError("Latitude and longitude are required.");
            return;
        }

        setSubmitting(true);
        try {
            const response = await submitComplaint({
                description: form.description,
                latitude: form.latitude,
                longitude: form.longitude,
                image,
                continueAsSeparate,
            });
            if (response?.requires_confirmation) {
                setDuplicateWarning(response);
                return;
            }
            setResult(response);
            setImage(null);
            if (response?.complaint_id !== undefined) {
                setTrackId(String(response.complaint_id));
            }
        } catch (err) {
            if (err?.detail?.type === "exact_image_duplicate") {
                setError(err.detail.message);
                setDuplicateComplaintId(err.detail.existing_complaint_id);
                setTrackId(String(err.detail.existing_complaint_id));
            } else {
                setError(err?.message || "Failed to submit complaint.");
            }
        } finally {
            setSubmitting(false);
        }
    }

    function handleReportAnother() {
        setResult(null);
        setImage(null);
        setForm((prev) => ({
            ...prev,
            description: "",
        }));
    }

    async function handleCheckStatus() {
        setTrackError("");
        setTrackResult(null);

        if (!trackId || trackId.trim() === "") {
            setTrackError("Enter a complaint ID.");
            return;
        }

        setTracking(true);
        try {
            const res = await fetch(
                `${API_BASE}/admin/complaints/${encodeURIComponent(trackId.trim())}`
            );

            if (!res.ok) {
                if (res.status === 404) {
                    setTrackError("No complaint found with that ID.");
                } else {
                    setTrackError(`Could not fetch complaint (${res.status}).`);
                }
                return;
            }

            const data = await res.json();
            setTrackResult(data);
        } catch (err) {
            setTrackError(err?.message || "Could not fetch complaint status.");
        } finally {
            setTracking(false);
        }
    }

    const roadAvailable =
        result?.road?.available !== undefined
            ? result.road.available
            : Boolean(result?.road?.name);

    return (
        <div className="citizen-page">
            <div className="citizen-shell">
                <button className="citizen-back" onClick={onBack} type="button">
                    <ArrowLeft size={15} />
                    Back to admin dashboard
                </button>

                <div className="citizen-header">
                    <span className="hero-eyebrow">CivicPriorityAI &middot; Vellore</span>
                    <h1>Report a Road Issue</h1>
                    <p>
                        Submit a road photo and location. YOLO identifies visible damage;
                        CivicPriority applies its damage-severity policy and calculates
                        overall repair priority separately.
                    </p>
                </div>

                <form className="citizen-form panel" onSubmit={handleSubmit}>
                    <label className="citizen-field">
                        <span>Description</span>
                        <textarea
                            rows={3}
                            placeholder="e.g. Large pothole near the bus stop"
                            value={form.description}
                            onChange={(e) => handleChange("description", e.target.value)}
                        />
                    </label>

                    <div className="citizen-field-row">
                        <label className="citizen-field">
                            <span>Latitude</span>
                            <input
                                type="number"
                                step="any"
                                required
                                placeholder="12.9165"
                                value={form.latitude}
                                onChange={(e) => handleChange("latitude", e.target.value)}
                            />
                        </label>
                        <label className="citizen-field">
                            <span>Longitude</span>
                            <input
                                type="number"
                                step="any"
                                required
                                placeholder="79.1325"
                                value={form.longitude}
                                onChange={(e) => handleChange("longitude", e.target.value)}
                            />
                        </label>
                    </div>

                    <div
                        style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                            flexWrap: "wrap",
                        }}
                    >
                        <button
                            type="button"
                            onClick={handleUseLocation}
                            disabled={locating}
                            style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "6px",
                                fontSize: "12px",
                                padding: "7px 12px",
                                borderRadius: "var(--radius-sm)",
                                border: "1px solid var(--line)",
                                background: "var(--bg-base)",
                                color: "var(--text-primary)",
                                cursor: locating ? "not-allowed" : "pointer",
                            }}
                        >
                            <LocateFixed size={14} />
                            {locating ? "Detecting…" : "Use My Location"}
                        </button>
                        {locationMessage && (
                            <span style={{ fontSize: "12px", color: "var(--accent-signal)" }}>
                                {locationMessage}
                            </span>
                        )}
                        {locationError && (
                            <span style={{ fontSize: "12px", color: "#e07a7a" }}>
                                {locationError}
                            </span>
                        )}
                    </div>

                    <label className="citizen-field">
                        <span>Road damage image</span>
                        <div className="citizen-file-input">
                            <Upload size={15} />
                            <input
                                type="file"
                                accept="image/png, image/jpeg, image/webp"
                                onChange={(e) => setImage(e.target.files?.[0] || null)}
                            />
                            <span>{image ? image.name : "Choose an image"}</span>
                        </div>
                    </label>

                    <button className="citizen-submit" type="submit" disabled={submitting}>
                        {submitting ? "Submitting…" : "Submit Complaint"}
                    </button>
                </form>

                {duplicateWarning && (
                    <div className="citizen-result panel" role="alert">
                        <div className="citizen-result-header"><AlertTriangle size={18} /><h2>Possible nearby report</h2></div>
                        <p>{duplicateWarning.message}</p>
                        <p>Existing complaint{duplicateWarning.possible_duplicates.length > 1 ? "s" : ""}: {duplicateWarning.possible_duplicates.map((item) => `#${item.complaint_id}`).join(", ")}</p>
                        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                            <button className="citizen-submit" type="button" onClick={() => setDuplicateWarning(null)}>Cancel</button>
                            <button className="citizen-submit" type="button" disabled={submitting} onClick={() => handleSubmit(null, true)}>{submitting ? "Submitting…" : "Continue as a separate issue"}</button>
                        </div>
                    </div>
                )}

                {error && (
                    <div className="error-banner strong citizen-alert">
                        <AlertTriangle size={16} />
                        {error}
                        {duplicateComplaintId && <button type="button" onClick={handleCheckStatus} style={{ marginLeft: 10 }}>View complaint #{duplicateComplaintId}</button>}
                    </div>
                )}

                {result && (
                    <div className="citizen-result panel">
                        <div className="citizen-result-header">
                            <CheckCircle2 size={18} />
                            <h2>Complaint Submitted</h2>
                        </div>
                        <h3>AI Analysis Image</h3>
                        {complaintImageUrl(result.annotated_image_path || result.image_path) && (
                            <img className="citizen-result-image" src={complaintImageUrl(result.annotated_image_path || result.image_path)} alt={`${result.annotated_image_path ? "AI annotated analysis" : "Original evidence; no reliable AI detection"} for complaint ${result.complaint_id}`} />
                        )}
                        {!result.annotated_image_path && result.image_path && <p className="citizen-detection-note">{result.annotation_error || (result.damage?.detection_state === "no_reliable_detection" ? "No reliable AI detection was available to annotate. The original upload is shown." : "AI detections could not be annotated; the original upload is shown.")}</p>}
                        <div className="citizen-result-grid">
                            <div>
                                <span>Complaint ID</span>
                                <strong>#{result.complaint_id}</strong>
                            </div>
                            <div>
                                <span>Road damage</span>
                                <strong>{roadDamageLabel(result.damage)}</strong>
                            </div>
                            <div>
                                <span>AI detection status</span>
                                <strong>{detectionStateLabel(result.damage)}</strong>
                            </div>
                            <div>
                                <span>Damage severity</span>
                                <strong>{damageSeverityLabel(result.damage)}</strong>
                            </div>
                            {result.damage?.confidence !== undefined && (
                                <div>
                                    <span>YOLO confidence</span>
                                    <strong>
                                        {yoloConfidenceLabel(result.damage)}
                                    </strong>
                                </div>
                            )}
                            <div>
                                <span>Overall priority</span>
                                <strong>{result.priority?.score ?? "—"}</strong>
                            </div>
                            <div>
                                <span>Overall priority level</span>
                                <strong>{result.priority?.level ?? "—"}</strong>
                            </div>
                            {result.priority?.recommended_action && (
                                <div>
                                    <span>Recommended action</span>
                                    <strong>{result.priority.recommended_action}</strong>
                                </div>
                            )}
                            <div>
                                <span>Road matching</span>
                                <strong>{roadAvailable ? "Available" : "Unavailable"}</strong>
                            </div>
                        </div>
                        {result.damage?.type === "unknown" && (
                            <p className="citizen-detection-note">
                                YOLO did not confirm a supported damage class at the 25% cutoff.
                                This does not prove the road is undamaged; the uploaded photo may
                                need human review. Overall priority is scored separately from
                                damage severity.
                            </p>
                        )}
                        {result.damage?.type === "unknown" && result.road?.type === "unclassified" && (
                            <p className="citizen-detection-note">
                                The matched road is marked unclassified in the road data, so local
                                road and facility context is limited. This can lower overall priority.
                            </p>
                        )}

                        <button
                            type="button"
                            className="citizen-submit"
                            style={{ marginTop: "16px" }}
                            onClick={handleReportAnother}
                        >
                            Report Another Issue
                        </button>
                    </div>
                )}

                <div className="citizen-result panel">
                    <div className="citizen-result-header">
                        <h2 style={{ color: "var(--text-primary)" }}>Track Complaint</h2>
                    </div>

                    <div
                        style={{
                            display: "flex",
                            gap: "10px",
                            alignItems: "flex-end",
                            flexWrap: "wrap",
                        }}
                    >
                        <label className="citizen-field" style={{ flex: 1, minWidth: "140px" }}>
                            <span>Complaint ID</span>
                            <input
                                type="text"
                                placeholder="e.g. 1"
                                value={trackId}
                                onChange={(e) => setTrackId(e.target.value)}
                            />
                        </label>
                        <button
                            type="button"
                            className="citizen-submit"
                            style={{ width: "auto" }}
                            onClick={handleCheckStatus}
                            disabled={tracking}
                        >
                            {tracking ? "Checking…" : "Check Status"}
                        </button>
                    </div>

                    {trackError && (
                        <div className="error-banner strong citizen-alert" style={{ marginTop: "12px" }}>
                            <AlertTriangle size={16} />
                            {trackError}
                        </div>
                    )}

                    {trackResult && (
                        <>
                        <div className="citizen-result-grid" style={{ marginTop: "14px" }}>
                            <div>
                                <span>Complaint ID</span>
                                <strong>#{trackResult.id}</strong>
                            </div>
                            <div>
                                <span>Status</span>
                                <strong>{trackResult.status ?? "—"}</strong>
                            </div>
                            <div>
                                <span>Overall priority level</span>
                                <strong>{trackResult.priority?.level ?? "—"}</strong>
                            </div>
                            <div>
                                <span>Overall priority score</span>
                                <strong>{trackResult.priority?.score ?? "—"}</strong>
                            </div>
                            <div>
                                <span>Road damage</span>
                                <strong>{roadDamageLabel(trackResult.damage)}</strong>
                            </div>
                            <div>
                                <span>Damage severity</span>
                                <strong>{damageSeverityLabel(trackResult.damage)}</strong>
                            </div>
                            {trackResult.road?.name && (
                                <div>
                                    <span>Road name</span>
                                    <strong>{trackResult.road.name}</strong>
                                </div>
                            )}
                        </div>
                        <h3>AI Analysis Image</h3>
                        {complaintImageUrl(trackResult.annotated_image_path || trackResult.image_path) && <img className="citizen-result-image" src={complaintImageUrl(trackResult.annotated_image_path || trackResult.image_path)} alt={`Analysis evidence for complaint ${trackResult.id}`} />}
                        {!trackResult.annotated_image_path && trackResult.image_path && <p className="citizen-detection-note">{trackResult.damage?.type === "unknown" ? "No reliable AI detection was available; the original image is shown." : "No saved AI-annotated image is available for this report; the original image is shown."}</p>}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
