import { useState } from "react";
import {
    IndianRupee,
    Layers,
    Loader2,
    AlertTriangle,
    MapPin,
} from "lucide-react";

import { complaintImageUrl as imageUrl, complaintNavigationUrl, assignTechnician, getBudgetOptimization } from "../api.js";
import { PriorityBadge } from "./StatusBadge.jsx";
import { damageSeverityLabel, detectionStateLabel, roadDamageLabel } from "../utils/complaintLabels.js";

const DEFAULT_BUDGET = 100000;

/**
 * Demo panel: shows that the system does more than rank complaints —
 * it selects an actual repair portfolio under a fixed budget, via the
 * existing GET /admin/optimization?budget=<n> endpoint (real 0/1
 * knapsack, solved server-side). This panel does not recompute
 * anything itself — it only calls the endpoint and displays the
 * result.
 */
export function BudgetOptimizerPanel({ technicians = [], onAssigned }) {
    const [budget, setBudget] = useState(DEFAULT_BUDGET);
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [selectedIds, setSelectedIds] = useState([]);
    const [technicianId, setTechnicianId] = useState("");
    const [assigning, setAssigning] = useState(false);
    const [notice, setNotice] = useState("");

    async function handleOptimize() {
        setLoading(true);
        setError("");
        try {
            const data = await getBudgetOptimization(budget);
            setResult(data);
            setSelectedIds((current) => current.filter((id) => data.selected_repairs?.some((repair) => repair.complaint_id === id)));
            setNotice("");
        } catch (err) {
            setResult(null);
            setError(
                err?.message || "Failed to run budget optimization."
            );
        } finally {
            setLoading(false);
        }
    }

    const repairs = result?.selected_repairs || [];

    async function handleAssignSelected() {
        const ids = selectedIds.filter((id) => repairs.some((repair) => repair.complaint_id === id));
        if (!technicianId || !ids.length) return;
        setAssigning(true);
        setError("");
        setNotice("");
        try {
            for (const id of ids) await assignTechnician(id, technicianId);
            setNotice(`${ids.length} budget-selected complaint${ids.length === 1 ? "" : "s"} assigned successfully.`);
            setSelectedIds([]);
            onAssigned?.();
        } catch (err) {
            setError(err?.message || "Could not assign the selected repairs.");
        } finally {
            setAssigning(false);
        }
    }

    return (
        <div className="panel budget-opt-panel">
            <div className="panel-header">
                <div>
                    <h2>Budget Optimization</h2>
                    <p>
                        0/1 knapsack selects an actual repair portfolio under a
                        fixed budget — not just a ranked list
                    </p>
                </div>
                {result && (
                    <span className="count-badge">
                        {result.selected_count} selected
                    </span>
                )}
            </div>

            <div className="budget-opt-controls">
                <label className="budget-opt-input">
                    <span>Available Budget (₹)</span>
                    <input
                        type="number"
                        min="0"
                        step="1000"
                        value={budget}
                        onChange={(e) => setBudget(Number(e.target.value))}
                    />
                </label>

                <button
                    type="button"
                    className="budget-opt-btn"
                    disabled={loading || !budget || budget <= 0}
                    onClick={handleOptimize}
                >
                    {loading ? (
                        <Loader2 size={14} className="spin" />
                    ) : (
                        <IndianRupee size={14} />
                    )}
                    {loading ? "Optimizing…" : "Optimize Budget"}
                </button>
            </div>

            {error && (
                <div className="error-banner">
                    <AlertTriangle size={14} />
                    {error}
                </div>
            )}
            {notice && <div className="success-banner" role="status">{notice}</div>}

            {!error && !result && !loading && (
                <div className="empty-state">
                    Enter a budget and run the optimizer to see the selected
                    repair portfolio.
                </div>
            )}

            {result && (
                <>
                    <div className="budget-opt-stats">
                        <div className="budget-opt-stat">
                            <span>Available Budget</span>
                            <strong>
                                ₹{Number(result.budget).toLocaleString("en-IN")}
                            </strong>
                        </div>
                        <div className="budget-opt-stat">
                            <span>Selected Repairs</span>
                            <strong>{result.selected_count}</strong>
                        </div>
                        <div className="budget-opt-stat">
                            <span>Total Repair Cost</span>
                            <strong>
                                ₹{Number(result.total_cost).toLocaleString("en-IN")}
                            </strong>
                        </div>
                        <div className="budget-opt-stat">
                            <span>Total Expected Impact</span>
                            <strong>{result.total_impact}</strong>
                        </div>
                        <div className="budget-opt-stat">
                            <span>Remaining Budget</span>
                            <strong>
                                ₹
                                {Number(result.remaining_budget).toLocaleString(
                                    "en-IN"
                                )}
                            </strong>
                        </div>
                    </div>

                    <div className="budget-opt-method">
                        <Layers size={13} />
                        0/1 Knapsack &mdash; Dynamic Programming
                    </div>

                    {repairs.length === 0 ? (
                        <div className="empty-state">
                            No repairs fit within this budget — try increasing it.
                        </div>
                    ) : (
                        <div className="budget-opt-list">
                            <div className="budget-assignment-controls">
                                <label className="budget-opt-input">
                                    <span>Assign selected repairs to</span>
                                    <select value={technicianId} onChange={(event) => setTechnicianId(event.target.value)}>
                                        <option value="">Choose technician…</option>
                                        {technicians.map((technician) => <option key={technician.id} value={technician.id}>{technician.name}</option>)}
                                    </select>
                                </label>
                                <button type="button" className="budget-opt-btn" disabled={assigning || !technicianId || selectedIds.length === 0} onClick={handleAssignSelected}>
                                    {assigning ? "Assigning…" : `Assign ${selectedIds.length} selected`}
                                </button>
                            </div>
                            {repairs.map((r) => (
                                <div className="budget-opt-item" key={r.complaint_id}>
                                    <div className="budget-opt-item-head">
                                        <label className="budget-repair-select"><input type="checkbox" checked={selectedIds.includes(r.complaint_id)} onChange={(event) => setSelectedIds((current) => event.target.checked ? [...new Set([...current, r.complaint_id])] : current.filter((id) => id !== r.complaint_id))} aria-label={`Select budget repair complaint ${r.complaint_id}`} /> Select</label>
                                        <span className="queue-id">
                                            #{String(r.complaint_id).padStart(3, "0")}
                                        </span>
                                        <span className="budget-priority-label">Overall priority</span><PriorityBadge level={r.priority_level} />
                                    </div>

                                    <div className="budget-opt-item-body">
                                        {imageUrl(r.annotated_image_path || r.image_path) && <a href={imageUrl(r.annotated_image_path || r.image_path)} target="_blank" rel="noreferrer" aria-label={`Open AI analysis image for complaint ${r.complaint_id}`}><img className="budget-repair-image" src={imageUrl(r.annotated_image_path || r.image_path)} alt={`AI analysis evidence for complaint ${r.complaint_id}`} /></a>}
                                        <div>
                                            <span>Impact score</span>
                                            <strong>{r.impact_score}</strong>
                                        </div>
                                        <div className="budget-repair-location">
                                            <span>Location</span>
                                            <strong>{r.latitude == null || r.longitude == null ? "Unavailable" : `${Number(r.latitude).toFixed(4)}, ${Number(r.longitude).toFixed(4)}`}</strong>
                                            {complaintNavigationUrl(r.latitude, r.longitude) && <a className="budget-location-link" href={complaintNavigationUrl(r.latitude, r.longitude)} target="_blank" rel="noreferrer"><MapPin size={13} />Navigate</a>}
                                        </div>
                                        <div>
                                            <span>Road</span>
                                            <strong>{r.road_name || r.road_type || "Unknown road"}</strong>
                                        </div>
                                        <div>
                                            <span>
                                                {r.cost_is_estimated
                                                    ? "Estimated Cost"
                                                    : "Actual Cost"}
                                            </span>
                                            <strong>
                                                ₹{Number(r.estimated_cost).toLocaleString(
                                                    "en-IN"
                                                )}
                                                {r.cost_is_estimated && (
                                                    <span className="estimate-tag">
                                                        ESTIMATE
                                                    </span>
                                                )}
                                            </strong>
                                        </div>
                                        {r.damage_type && (
                                            <div>
                                                <span>Road damage</span>
                                                <strong>{roadDamageLabel({ type: r.damage_type, confidence: r.confidence, detection_state: r.detection_state })}</strong>
                                            </div>
                                        )}
                                        {r.severity && (
                                            <div>
                                                <span>Damage severity</span>
                                                <strong>{damageSeverityLabel({ type: r.damage_type, severity: r.severity, confidence: r.confidence, detection_state: r.detection_state })}</strong>
                                            </div>
                                        )}
                                        <div><span>AI detection state</span><strong>{detectionStateLabel({ type: r.damage_type, confidence: r.confidence, detection_state: r.detection_state })}</strong></div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
