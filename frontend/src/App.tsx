import { useEffect, useRef, useState } from "react";
import { Dashboard } from "./components/Dashboard";
import { Sidebar, navLabels, type NavKey } from "./components/Sidebar";
import { ClubCrest } from "./components/ClubCrest";
import { Icon } from "./components/Icon";

type Overlay = { title: string; detail: string; category?: string };

// Deliberately UI-only date: never call this a world/season advance.
const initialPreviewDay = "2027-05-01";
const fmt = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });

function advanceIsoDay(iso: string) {
  const date = new Date(`${iso}T00:00:00.000Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}

function Dialog({ overlay, close }: { overlay: Overlay; close: () => void }) {
  useEffect(() => {
    const onEscape = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [close]);

  return (
    <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) close(); }}>
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
        <div className="modal-top"><span className="modal-category">{overlay.category ?? "FM Project"}</span><button aria-label="Close dialog" type="button" onClick={close} className="icon-button"><Icon name="close" size={20}/></button></div>
        <h2 id="dialog-title">{overlay.title}</h2>
        <p>{overlay.detail}</p>
        <div className="modal-footer"><button type="button" className="action-green" onClick={close}>Got it <Icon name="check" size={17}/></button></div>
      </section>
    </div>
  );
}

function PlaceholderPage({ name, onHome }: { name: string; onHome: () => void }) {
  return (
    <div className="placeholder-page panel">
      <div className="placeholder-emblem"><Icon name="tactics" size={46}/></div>
      <span className="eyebrow">COMING LATER</span>
      <h2>{name}</h2>
      <p>This section is not ready yet. The Python simulation remains unchanged; Squad and Tactics are connected to the development session.</p>
      <button className="action-green" type="button" onClick={onHome}><Icon name="home" size={17}/> Back to Home</button>
    </div>
  );
}

function App() {
  const [page, setPage] = useState<NavKey>("home");
  const [devDate, setDevDate] = useState<string | null>(null);
  const squadFrameRef = useRef<HTMLIFrameElement>(null);
  useEffect(() => {
    if (page === "squad" || page === "tactics") {
      squadFrameRef.current?.contentWindow?.postMessage({ type: "fm-open-squad", view: page }, window.location.origin);
    }
  }, [page]);
  useEffect(() => {
    const onFrameRoute = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      if (event.data?.type === "fm-squad-state" && /^\d{4}-\d{2}-\d{2}$/.test(event.data.date)) {
        setDevDate(event.data.date);
      }
      if (event.data?.type === "fm-squad-route" && (event.data.page === "tactics" || event.data.page === "squad")) {
        setPage(event.data.page);
      }
    };
    window.addEventListener("message", onFrameRoute);
    return () => window.removeEventListener("message", onFrameRoute);
  }, []);
  const [previewDay, setPreviewDay] = useState(initialPreviewDay);
  const [overlay, setOverlay] = useState<Overlay | null>(null);
  const [dayNote, setDayNote] = useState(false);
  const date = fmt.format(new Date(`${previewDay}T00:00:00.000Z`));
  const activeDate = (page === "squad" || page === "tactics") && devDate ? fmt.format(new Date(`${devDate}T00:00:00.000Z`)) : date;

  function nextDay() {
    setPreviewDay(current => advanceIsoDay(current));
    setDayNote(true);
  }

  return (
    <div className="app-shell">
      <Sidebar current={page} onChange={setPage} dateLabel={activeDate} />
      <main className="main-content">
        <header className="app-header">
          <div className="header-left">
            <div className="heading-row"><h1>{page === "home" ? "Home" : navLabels[page]}</h1><span className="preview-label">{page === "squad" || page === "tactics" ? "UI-2 · PYTHON DEV" : "UI-1 · DEMO"}</span></div>
            <p>{page === "home" ? "Welcome to Northbridge FC. An overview of your club, upcoming fixtures and key information." : "Python development session · real squad, roles and tactics; Home remains a demo."}</p>
          </div>
          <div className="header-actions">
            <div className="club-identity"><ClubCrest variant="northbridge" size={36} /><span><strong>Northbridge FC</strong><small>{activeDate}</small></span></div>
            <button className="continue-button" type="button" onClick={nextDay} disabled={page !== "home"} title={page === "home" ? "Demo date only; not the Python world" : "Python daily Continue not implemented yet"}>
              Continue <Icon name="chevron" size={22}/>
            </button>
            <button className="header-icon-button" type="button" aria-label="Preview information" onClick={() => setOverlay({ title: "About this preview", detail: "UI-1 is a React + TypeScript visual prototype with fictional sample data. The Continue button changes the displayed demo date one day at a time. It does not simulate fixtures, update players, or save a game. Those actions will be implemented by Python services in a separate integration phase.", category: "UI-1 — Prototype" })}><Icon name="sparkles" size={20}/></button>
          </div>
        </header>
        {dayNote && (
          <div className="preview-notice" role="status">
            <Icon name="alert" size={17}/>
            <span><strong>Preview only:</strong> date advanced by one day. Python world, fixtures and player state were not changed.</span>
            <button type="button" onClick={() => setDayNote(false)} aria-label="Dismiss preview notice"><Icon name="close" size={15}/></button>
          </div>
        )}
        {page === "home" ? (
          <Dashboard onViewTactics={() => setPage("tactics")} onOpen={setOverlay}/>
        ) : page === "squad" || page === "tactics" ? (
          <iframe ref={squadFrameRef} className="fm-squad-frame" src="/squad/embed.html?view=squad" title="Squad roster and tactics" onLoad={() => squadFrameRef.current?.contentWindow?.postMessage({ type: "fm-open-squad", view: page }, window.location.origin)} />
        ) : (
          <PlaceholderPage name={navLabels[page]} onHome={() => setPage("home")}/>
        )}
        <footer className="app-footer"><span>FM Project · UI-2 Preview</span><span>Home: fictional demo · Squad & Tactics: Python DEV session</span></footer>
      </main>
      {overlay && <Dialog overlay={overlay} close={() => setOverlay(null)} />}
    </div>
  );
}

export default App;
