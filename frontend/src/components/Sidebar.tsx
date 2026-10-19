import { Icon, type IconName } from "./Icon";

export type NavKey =
  | "home" | "squad" | "tactics" | "calendar" | "competitions"
  | "scouting" | "transfers" | "club" | "finances" | "staff"
  | "training" | "medical" | "inbox";

const sections: { id: NavKey; label: string; icon: IconName; badge?: number }[] = [
  { id: "home", label: "Home", icon: "home" },
  { id: "squad", label: "Squad", icon: "users" },
  { id: "tactics", label: "Tactics", icon: "tactics" },
  { id: "calendar", label: "Calendar", icon: "calendar" },
  { id: "competitions", label: "Competitions", icon: "trophy" },
  { id: "scouting", label: "Scouting", icon: "search" },
  { id: "transfers", label: "Transfers", icon: "transfer" },
  { id: "club", label: "Club Info", icon: "shield" },
  { id: "finances", label: "Finances", icon: "wallet" },
  { id: "staff", label: "Staff", icon: "staff" },
  { id: "training", label: "Training", icon: "training" },
  { id: "medical", label: "Medical Centre", icon: "medical" },
  { id: "inbox", label: "Inbox", icon: "inbox", badge: 2 },
];

export const navLabels: Record<NavKey, string> = Object.fromEntries(sections.map(item => [item.id, item.label])) as Record<NavKey, string>;

export function Sidebar({ current, onChange, dateLabel }: { current: NavKey; onChange: (key: NavKey) => void; dateLabel: string }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark"><Icon name="shield" size={28} /><span>V</span></div>
        <div><div className="brand-name">FM PROJECT</div><div className="brand-sub">FOOTBALL MANAGER</div></div>
      </div>
      <nav className="sidebar-links" aria-label="Main navigation">
        {sections.map(item => (
          <button
            className={`nav-item ${current === item.id ? "is-active" : ""}`}
            type="button"
            key={item.id}
            aria-current={current === item.id ? "page" : undefined}
            onClick={() => onChange(item.id)}
          >
            <Icon name={item.icon} size={19} />
            <span>{item.label}</span>
            {item.badge ? <span className="nav-badge">{item.badge}</span> : null}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <span className="sidebar-bottom-icon"><Icon name="calendar" size={18} /></span>
        <div><strong>{dateLabel}</strong><span>Demo calendar • UI-1</span></div>
        <Icon name="chevron" size={16} />
      </div>
    </aside>
  );
}
