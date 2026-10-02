export function StatCard({ label, value, icon: Icon, tone = "neutral" }) {
  return (
    <div className={`stat-card tone-${tone}`}>
      <div className="stat-card-top">
        <span className="stat-label">{label}</span>
        {Icon && <Icon size={15} strokeWidth={1.75} />}
      </div>
      <div className="stat-value">{value}</div>
    </div>
  );
}
