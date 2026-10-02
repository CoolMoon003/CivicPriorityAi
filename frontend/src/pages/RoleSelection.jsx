import { useEffect, useState } from "react";
import { ArrowRight, HardHat, ShieldCheck, UserRound } from "lucide-react";
import { API_BASE } from "../api.js";

export function RoleSelection({ onSelect }) {
  const [apiState, setApiState] = useState("checking");
  useEffect(() => {
    fetch(`${API_BASE}/`).then((response) => {
      if (!response.ok) throw new Error("offline");
      setApiState("online");
    }).catch(() => setApiState("offline"));
  }, []);

  const roles = [
    { id: "citizen", title: "Citizen / User", description: "Report road issues and follow your complaints.", icon: UserRound, tint: "citizen" },
    { id: "admin", title: "Admin", description: "Review priorities, assign repairs, and manage operations.", icon: ShieldCheck, tint: "admin" },
    { id: "technician", title: "Technician", description: "View assigned work and update repair progress.", icon: HardHat, tint: "technician" },
  ];

  return <main className="role-select-page">
    <div className="role-select-shell">
      <div className="role-brand"><div className="brand-mark">CP</div><div><strong>CivicPriority AI</strong><span>Vellore · Tamil Nadu</span></div></div>
      <div className="role-select-heading"><span className="hero-eyebrow">Civic road operations</span><h1>Who is using CivicPriority AI?</h1><p>Choose a demo workspace to continue. This prototype does not authenticate users or enforce role permissions.</p></div>
      <div className="role-card-grid">
        {roles.map(({ id, title, description, icon: Icon, tint }) => <button key={id} className={`role-card ${tint}`} onClick={() => onSelect(id)}>
          <span className="role-card-icon"><Icon size={23} /></span><span className="role-card-copy"><strong>{title}</strong><small>{description}</small></span><ArrowRight className="role-card-arrow" size={17} />
        </button>)}
      </div>
      <div className={`role-api-state ${apiState}`}><span className="status-dot" />{apiState === "checking" ? "Checking service…" : apiState === "online" ? "CivicPriority API connected" : "API unavailable · you can still choose a role"}</div>
      <small className="role-select-foot">AI-assisted civic road maintenance · CivicPriority AI</small>
    </div>
  </main>;
}
