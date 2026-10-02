const configuredApiBase = import.meta.env.VITE_API_BASE_URL
  || (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");
export const API_BASE = configuredApiBase.replace(/\/+$/, "");

export function complaintImageUrl(path) {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  const normalized = String(path).replace(/\\/g, "/");
  const uploadPart = normalized.match(/(?:^|\/)data\/uploads\/(.+)$/i)?.[1]
    || normalized.match(/^\/?uploads\/(.+)$/i)?.[1]
    || normalized.split("/").pop();
  if (!uploadPart) return null;
  return `${API_BASE}/uploads/${uploadPart.split("/").map(encodeURIComponent).join("/")}`;
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);

  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body?.detail ? JSON.stringify(body.detail) : "";
    } catch {
      /* ignore parse errors */
    }
    const error = new Error(detail || `Request failed (${res.status}) ${path}`);
    error.status = res.status;
    try { error.detail = JSON.parse(detail); } catch { error.detail = null; }
    throw error;
  }

  return res.json();
}

export function getDashboard() {
  return request("/admin/dashboard");
}

export function getComplaints() {
  return request("/admin/complaints");
}

export function getPriorities() {
  return request("/admin/priorities?limit=500");
}

export function getComplaint(id) {
  return request(`/admin/complaints/${id}`);
}

export function updateComplaintStatus(id, status) {
  return request(
    `/admin/complaints/${id}/status?status=${encodeURIComponent(status)}`,
    { method: "PATCH" }
  );
}

export function deleteComplaint(id, adminToken) {
  return request(`/admin/complaints/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: { "X-Civic-Admin-Token": adminToken },
  });
}

export function assignTechnician(id, technicianId) {
  return request(
    `/admin/complaints/${id}/assign?technician_id=${encodeURIComponent(
      technicianId
    )}`,
    { method: "PATCH" }
  );
}

export function getTechnicians() {
  return request("/technicians/");
}

export function getTechnicianComplaints(technicianId) {
  return request(`/technicians/${encodeURIComponent(technicianId)}/complaints`);
}

export function updateTechnicianComplaintStatus(technicianId, complaintId, status) {
  return request(`/technicians/${encodeURIComponent(technicianId)}/complaints/${encodeURIComponent(complaintId)}/status?status=${encodeURIComponent(status)}`, { method: "PATCH" });
}

export function createRepairRecord(complaintId, { technicianId, repairNotes, repairCost }) {
  const query = new URLSearchParams({ technician_id: technicianId, repair_notes: repairNotes || "" });
  if (repairCost !== "" && repairCost != null) query.set("repair_cost", String(repairCost));
  return request(`/outcomes/repairs/${encodeURIComponent(complaintId)}?${query}`, { method: "POST" });
}

export function getComplaintOutcomes(complaintId) {
  return request(`/outcomes/complaints/${encodeURIComponent(complaintId)}`);
}

export function verifyRepair(repairId, approved, verificationNotes = "") {
  const query = new URLSearchParams({ approved: String(approved), verification_notes: verificationNotes });
  return request(`/outcomes/repairs/${encodeURIComponent(repairId)}/verify?${query}`, { method: "PATCH" });
}

export function getBudgetOptimization(budget) {
  return request(`/admin/optimization?budget=${encodeURIComponent(budget)}`);
}

export function submitComplaint({ description, latitude, longitude, image, userId, continueAsSeparate = false }) {
  const formData = new FormData();
  formData.append("latitude", latitude);
  formData.append("longitude", longitude);
  formData.append("description", description ?? "");
  if (userId != null) formData.append("user_id", String(userId));
  formData.append("continue_as_separate", String(continueAsSeparate));

  if (image) {
    formData.append("image", image);
  }

  return request("/complaints/", {
    method: "POST",
    body: formData,
  });
}

export function createCitizenProfile({ name, email, phone }) {
  return request("/citizen/profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, phone: phone || null }),
  });
}

export function getCitizenProfile(userId) {
  return request(`/citizen/profiles/${encodeURIComponent(userId)}`);
}

export function getCitizenComplaints(userId) {
  return request(`/citizen/${encodeURIComponent(userId)}/complaints`);
}

export function getCitizenComplaint(userId, complaintId) {
  return request(`/citizen/${encodeURIComponent(userId)}/complaints/${encodeURIComponent(complaintId)}`);
}
