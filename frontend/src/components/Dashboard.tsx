import { useState } from "react";
import { ClubCrest, SmallCrest } from "./ClubCrest";
import { Icon } from "./Icon";
import { competitions, demoDashboard, type ClubStory, type Competition, type LineupPlayer, type Notification } from "../data/dashboard";

type OpenItem = { title: string; detail: string; category?: string };

const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });

export function ClubHero() {
  const c = demoDashboard.club;
  return (
    <section className="panel hero-card" aria-labelledby="club-title">
      <div className="hero-body">
        <div className="hero-crest"><ClubCrest variant="northbridge" size={111} /></div>
        <div className="hero-primary">
          <div className="hero-eyebrow">NORTHBRIDGE FC</div>
          <h2 id="club-title">{c.name}</h2>
          <div className="hero-subtitle"><span className="england-flag" aria-hidden="true" /> {c.league}</div>
          <div className="hero-manager">Manager <strong>{c.manager}</strong></div>
          <div className="hero-highlights">
            <div><strong>{c.position}</strong><span>League position</span></div>
            <div><strong>{c.points}</strong><span>Points</span></div>
            <div className="hero-form"><span>Recent form</span><div className="form-dots" aria-label="Recent form: win, win, draw, win, loss">
              {c.recentResults.map((result, index) => <span className={`form-dot dot-${result.toLowerCase()}`} key={`${result}-${index}`}>{result}</span>)}
            </div></div>
          </div>
        </div>
      </div>
      <div className="hero-footer">
        <div className="hero-fact"><Icon name="calendar" size={24} /><span><strong>{c.season}</strong><small>Season</small></span></div>
        <div className="hero-fact"><Icon name="shield" size={24} /><span><strong>{c.clubStatus}</strong><small>Club status</small></span></div>
        <div className="hero-fact"><Icon name="stadium" size={24} /><span><strong>{c.capacity}</strong><small>Stadium capacity</small></span></div>
        <div className="hero-fact hero-objective"><Icon name="target" size={25} /><span><strong>{c.objective}</strong><small>Season objective</small></span></div>
      </div>
    </section>
  );
}

export function NextMatch({ onPreview }: { onPreview: () => void }) {
  const m = demoDashboard.nextMatch;
  return (
    <section className="panel next-match" aria-labelledby="next-match-title">
      <div className="section-heading match-heading"><h2 id="next-match-title">Next Match</h2><span className="competition-badge">{m.competition}</span></div>
      <div className="versus-area">
        <div className="versus-team"><ClubCrest variant="northbridge" size={78} /><strong>Northbridge FC</strong><small>{m.isHome ? "Home" : "Away"}</small></div>
        <div className="versus-text">VS</div>
        <div className="versus-team"><ClubCrest variant="redhaven" size={78} /><strong>{m.opponent}</strong><small>{m.isHome ? "Away" : "Home"}</small></div>
      </div>
      <div className="match-bottom">
        <span><Icon name="calendar" size={18} /> Sat {dateFmt.format(new Date(`${m.isoDate}T00:00:00Z`))}</span>
        <span><Icon name="clock" size={18} /> {m.kickoff}</span>
        <span className="match-venue"><Icon name="stadium" size={18} /> {m.stadium}</span>
        <button type="button" className="action-green" onClick={onPreview}>Match Preview <Icon name="arrow" size={17} /></button>
      </div>
    </section>
  );
}

function TableRow({ row, index }: { row: NonNullable<Competition["table"]>[number]; index: number }) {
  return (
    <div className={`league-row ${row.clubId === "northbridge" ? "is-managed" : ""}`}>
      <span className="row-pos">{index + 1}</span>
      <span className="row-club"><SmallCrest name={row.name} color={row.accent} /><span>{row.name}</span></span>
      <span>{row.played}</span><span>{row.won}</span><span>{row.drawn}</span><span>{row.lost}</span>
      <span>{row.goalDifference > 0 ? `+${row.goalDifference}` : row.goalDifference}</span><strong>{row.points}</strong>
    </div>
  );
}

export function LeagueBoard() {
  const [selected, setSelected] = useState(competitions[0].id);
  const active = competitions.find(item => item.id === selected) ?? competitions[0];
  const rows = active.table ?? [];
  return (
    <section className="panel league-card" aria-labelledby="league-title">
      <div className="section-heading"><h2 id="league-title">{active.kind === "league" ? "League Table" : "Cup Progress"}</h2><span className="card-kicker">{active.kind === "league" ? "League table" : "Knockout cup"}</span></div>
      <div className="competition-tabs" role="tablist" aria-label="Competition">
        {competitions.map(item => (
          <button
            key={item.id}
            role="tab"
            id={`tab-${item.id}`}
            aria-controls="competition-panel"
            aria-selected={selected === item.id}
            className={`competition-tab ${selected === item.id ? "selected" : ""}`}
            type="button"
            onClick={() => setSelected(item.id)}
          >{item.title}</button>
        ))}
      </div>
      <div role="tabpanel" id="competition-panel" aria-labelledby={`tab-${active.id}`} className="table-body">
        {active.kind === "league" ? (
          <>
            <div className="league-row league-header"><span>POS</span><span>TEAM</span><span>P</span><span>W</span><span>D</span><span>L</span><span>GD</span><span>PTS</span></div>
            {rows.map((row, index) => (
              <div key={row.clubId} className={index === 6 ? "row-break" : ""}>
                {index === 6 && <div className="league-ellipsis" aria-label="Table abbreviated">••• <small>Other positions omitted in preview</small></div>}
                <TableRow row={row} index={index < 6 ? index : index + (active.id === "premier" ? 6 : 0)} />
              </div>
            ))}
            <div className="table-note"><Icon name="sparkles" size={14} /> Fictional UI-1 standings • not Python results</div>
          </>
        ) : (
          <div className="cup-panel">
            <Icon name="trophy" size={52} />
            <span className="cup-label">{active.title}</span>
            <h3>{active.cupProgress?.stage}</h3>
            <p>{active.cupProgress?.description}</p>
            <div className="cup-fixture"><Icon name="football" size={20} /><span>{active.cupProgress?.nextTie}</span></div>
            <small>Example knockout data. Brackets will be read from Python in UI-2.</small>
          </div>
        )}
      </div>
    </section>
  );
}

function PlayerPortrait({ player }: { player: LineupPlayer }) {
  return (
    <svg className="player-portrait" viewBox="0 0 52 53" aria-hidden="true">
      <defs><linearGradient id={`shirt-${player.id}`} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#233e54" /><stop offset="1" stopColor="#071c2d" /></linearGradient></defs>
      <path d="M2 53v-7q0-10 10-13l9-3h10l9 3q10 3 10 13v7" fill={`url(#shirt-${player.id})`} stroke="#6dbac1" strokeWidth="1" />
      <path d="M21 28v9l5 5 5-5v-9" fill={player.skin} />
      <ellipse cx="26" cy="20" rx="12" ry="15" fill={player.skin} />
      <path d="M14 22c-3-10 3-19 13-19 11 0 15 9 11 20l-2-8c-3-1-6-4-7-5-4 5-10 5-13 5Z" fill={player.hair} />
      <path d="M19 21h3M30 21h3" stroke="#292321" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M23 29q3 2 6 0" stroke="#723f34" strokeWidth="1" fill="none" strokeLinecap="round" />
      <path d="M18 34q8 8 16 0" stroke="#d5e9e6" strokeWidth="1.3" fill="none" />
    </svg>
  );
}

function StartingPlayer({ player }: { player: LineupPlayer }) {
  return (
    <div className="pitch-player" style={{ left: `${player.x}%`, top: `${player.y}%` }} title={`${player.name} • ${player.position} • OVR ${player.overall.toFixed(1).replace('.', ',')}`}>
      <div className="player-photo"><PlayerPortrait player={player} /><span className="ovr-tag" aria-label={`OVR ${player.overall.toFixed(1).replace('.', ',')}`}>{player.overall.toFixed(1).replace('.', ',')}</span></div>
      <div className="player-info"><small>{player.position}</small><strong>{player.name}</strong></div>
    </div>
  );
}

export function TacticalOverview({ onViewTactics }: { onViewTactics: () => void }) {
  const data = demoDashboard;
  return (
    <section className="panel tactics-card" aria-labelledby="tactics-title">
      <div className="section-heading"><h2 id="tactics-title">Tactical Overview</h2><button className="text-action" type="button" onClick={onViewTactics}>View Tactics <Icon name="chevron" size={16} /></button></div>
      <div className="mini-metrics">
        {data.teamMetrics.map(metric => (
          <div className="metric-tile" key={metric.key}>
            <div className="metric-detail"><span className={`metric-icon ${metric.color}`}><Icon name={metric.icon} size={21}/></span><div><small>{metric.label}</small><strong>{metric.word}</strong></div></div>
            <div className="metric-bottom"><div className="metric-track"><div className={`metric-fill ${metric.color}`} style={{ width: `${metric.score}%` }} /></div><span>{metric.score}</span></div>
          </div>
        ))}
      </div>
      <div className="formation-strip">
        <div className="formation-name"><Icon name="tactics" size={20} /><strong>{data.formation} <span>{data.mentality}</span></strong></div>
        <div className="formation-diagnostics"><span className="lineup-ready"><Icon name="check" size={15} /> 11/11 selected</span><span className="lineup-alert"><Icon name="alert" size={16} /> 2 players tired</span></div>
      </div>
      <div className="pitch" aria-label="Starting eleven visualized in a four-three-three formation. Values displayed are overall ratings, not match ratings.">
        <div className="pitch-grass" />
        <div className="pitch-markings"><div className="midline"/><div className="center-circle"/><div className="top-box"/><div className="top-six"/><div className="bottom-box"/><div className="bottom-six"/></div>
        {data.lineupPlayers.map(player => <StartingPlayer player={player} key={player.id} />)}
      </div>
      <div className="tactics-caption"><Icon name="check" size={14} /> Player number = overall rating (OVR), not match performance</div>
    </section>
  );
}

const notificationIcons: Record<Notification["category"], { icon: "mail" | "medical" | "users" | "search" | "news"; color: string }> = {
  player: { icon: "mail", color: "purple" },
  medical: { icon: "medical", color: "rose" },
  team: { icon: "users", color: "blue" },
  scouting: { icon: "search", color: "green" },
  board: { icon: "news", color: "gold" },
};

function NotificationRow({ notification, onOpen }: { notification: Notification; onOpen: (item: OpenItem) => void }) {
  const visual = notificationIcons[notification.category];
  return (
    <button className="notification-row" type="button" onClick={() => onOpen({ title: notification.title, detail: notification.details, category: "Inbox message • Demo" })}>
      <span className={`notification-icon ${visual.color}`}><Icon name={visual.icon} size={20} /></span>
      <span className="notification-copy"><strong>{notification.title}</strong><span>{notification.preview}</span></span>
      <span className="notification-meta"><small>{notification.time}</small>{notification.unread ? <i className="unread-dot" aria-label="Unread" /> : <Icon name="chevron" size={14} />}</span>
    </button>
  );
}

function StoryArtwork({ type }: { type: ClubStory["type"] }) {
  if (type === "stadium") return <div className="story-art stadium-story" />;
  return <div className={`story-art story-${type}`}><Icon name={type === "trophy" ? "trophy" : type === "star" ? "sparkles" : "tactics"} size={40}/></div>;
}

function StoryCard({ story, featured, onOpen }: { story: ClubStory; featured: boolean; onOpen: (item: OpenItem) => void }) {
  return (
    <button
      type="button"
      className={`story-card ${featured ? "is-featured" : ""}`}
      onClick={() => onOpen({ title: story.title, detail: story.preview, category: `${story.category} • ${story.time} • Demo story` })}
    >
      <StoryArtwork type={story.type} />
      <span className="story-copy"><span className="story-category">{story.category}</span><strong>{story.title}</strong><small>{story.time}</small></span>
    </button>
  );
}

export function ActivityPanel({ onOpen }: { onOpen: (item: OpenItem) => void }) {
  const [view, setView] = useState<"inbox" | "stories">("inbox");
  const all = demoDashboard.notifications;
  const storyItems = demoDashboard.stories;
  return (
    <div className="activity-column">
      <section className="panel inbox-card" aria-label="Inbox and club news">
        <div className="section-heading activity-heading">
          <div className="activity-tabs" role="tablist" aria-label="Updates category">
            <button role="tab" aria-selected={view === "inbox"} aria-controls="activity-panel" onClick={() => setView("inbox")} className={view === "inbox" ? "active" : ""} type="button" id="activity-inbox">Inbox <span className="unread-count">2</span></button>
            <button role="tab" aria-selected={view === "stories"} aria-controls="activity-panel" onClick={() => setView("stories")} className={view === "stories" ? "active" : ""} type="button" id="activity-stories">Club News</button>
          </div>
          <button className="text-action" type="button" onClick={() => onOpen({ title: view === "inbox" ? "Inbox & Notifications" : "Club News", detail: "This is an interactive UI-1 preview. Real notifications and generated news will be integrated through the Python event system in a later phase.", category: "UI preview" })}>View All <Icon name="chevron" size={15} /></button>
        </div>
        <div role="tabpanel" aria-labelledby={view === "inbox" ? "activity-inbox" : "activity-stories"} id="activity-panel" className="notifications-list">
          {view === "inbox"
            ? all.map(n => <NotificationRow key={n.id} notification={n} onOpen={onOpen} />)
            : storyItems.map(s => <button className="notification-row" type="button" key={s.id} onClick={() => onOpen({ title: s.title, detail: s.preview, category: s.category })}><span className="notification-icon purple"><Icon name="news" /></span><span className="notification-copy"><strong>{s.title}</strong><span>{s.preview}</span></span><Icon name="chevron" size={14}/></button>)}
        </div>
      </section>
      <section className="panel club-news" aria-labelledby="news-title">
        <div className="section-heading"><h2 id="news-title">Club News</h2><button className="text-action" type="button" onClick={() => setView("stories")}>Explore Stories <Icon name="chevron" size={15} /></button></div>
        <div className="story-grid">
          {storyItems.map((story, i) => <StoryCard key={story.id} story={story} featured={i === 0} onOpen={onOpen} />)}
        </div>
      </section>
    </div>
  );
}

export function Dashboard({ onViewTactics, onOpen }: { onViewTactics: () => void; onOpen: (item: OpenItem) => void }) {
  return (
    <div className="dashboard-grid">
      <div className="top-grid"><ClubHero/><NextMatch onPreview={() => onOpen({ title: "Northbridge FC vs Redhaven FC", detail: "Premier League • Saturday 8 May 2027 • 15:00 • Northbridge Stadium. Match preview is a visual prototype. The fixture will be connected to the Python SeasonCalendar and FastMatchSimulator in a later UI integration phase.", category: "Match Preview • Demo" })}/></div>
      <div className="widgets-grid"><LeagueBoard/><TacticalOverview onViewTactics={onViewTactics}/><ActivityPanel onOpen={onOpen}/></div>
    </div>
  );
}
