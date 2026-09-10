import { Suspense, lazy, useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { Loading, initials } from "./components/common";
import {
  IconBarChart,
  IconCamera,
  IconClose,
  IconDashboard,
  IconFileText,
  IconFolder,
  IconList,
  IconLock,
  IconMenu,
  IconPlus,
  IconShieldCheck,
  IconSliders,
} from "./components/icons";
import { useI18n, type Lang } from "./i18n";
import { useOfficerName } from "./officer";
import { useQueueStatus } from "./offlineQueue";
import Capture from "./pages/Capture";
import Cases from "./pages/Cases";
import Entity from "./pages/Entity";
import Ledger from "./pages/Ledger";
import Report from "./pages/Report";
import Rules from "./pages/Rules";
import ScanDetail from "./pages/ScanDetail";
import Scans from "./pages/Scans";
import Settings from "./pages/Settings";
import Dashboard from "./pages/Dashboard";
import Worklist from "./pages/Worklist";

// Recharts is the single heaviest dependency in the bundle; officers mostly capture
// and review, so Analytics — the one page that needs it — loads on demand instead of
// adding its weight to every page on a poor-connectivity field connection.
const Analytics = lazy(() => import("./pages/Analytics"));

const NAV_ITEMS = [
  { to: "/", key: "nav.dashboard", icon: IconDashboard, end: true },
  { to: "/inspections", key: "nav.inspections", icon: IconList, end: false },
  { to: "/cases", key: "nav.cases", icon: IconFolder, end: false },
  { to: "/compliance", key: "nav.compliance", icon: IconShieldCheck, end: false },
  { to: "/evidence", key: "nav.evidence", icon: IconLock, end: false },
  { to: "/reports", key: "nav.reports", icon: IconFileText, end: false },
  { to: "/analytics", key: "nav.analytics", icon: IconBarChart, end: false },
  { to: "/settings", key: "nav.settings", icon: IconSliders, end: false },
] as const;

interface SidebarProps {
  officerName: string;
  lang: Lang;
  setLang: (lang: Lang) => void;
  queueCount: number;
  online: boolean;
  onNavigate?: () => void;
  onClose?: () => void;
}

function Sidebar({ officerName, lang, setLang, queueCount, online, onNavigate, onClose }: SidebarProps) {
  const { t } = useI18n();
  return (
    <>
      <div className="sidebar-brand">
        <NavLink to="/" className="brand-mark" aria-hidden="true" onClick={onNavigate}>
          LL
        </NavLink>
        <div className="brand-text">
          <strong>{t("app.name")}</strong>
          <span>{t("app.tagline")}</span>
        </div>
        {onClose && (
          <button className="drawer-close" onClick={onClose} aria-label={t("common.close")}>
            <IconClose size={20} />
          </button>
        )}
      </div>

      <div className="sidebar-primary">
        <NavLink to="/inspect" className="btn btn-primary btn-block" onClick={onNavigate}>
          <IconCamera size={16} />
          {t("nav.inspect")}
        </NavLink>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ to, key, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} onClick={onNavigate}>
            <Icon size={16} />
            {t(key)}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-foot">
        <div className="sidebar-officer">
          <span className="officer-avatar">{initials(officerName || "?")}</span>
          <div className="sidebar-officer-info">
            <strong>{officerName || "Not set"}</strong>
            <span>{t("settings.officerName")}</span>
          </div>
        </div>

        <div className="sidebar-sync">
          <span className={`sync-dot${online ? "" : " offline"}`} aria-hidden="true" />
          {queueCount > 0
            ? `${queueCount} held offline`
            : online
              ? "Synced"
              : "Offline"}
        </div>

        <div className="lang-toggle">
          <button aria-pressed={lang === "en"} onClick={() => setLang("en")}>
            EN
          </button>
          <button aria-pressed={lang === "hi"} onClick={() => setLang("hi")}>
            हिं
          </button>
        </div>
      </div>
    </>
  );
}

export default function App() {
  const { lang, setLang } = useI18n();
  const { name: officerName, setName: setOfficerName } = useOfficerName();
  const queue = useQueueStatus();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  const sidebarProps: SidebarProps = {
    officerName,
    lang,
    setLang,
    queueCount: queue.count,
    online: queue.online,
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Sidebar {...sidebarProps} />
      </aside>

      <header className="topbar">
        <button className="topbar-menu" onClick={() => setDrawerOpen(true)} aria-label="Open menu">
          <IconMenu size={22} />
        </button>
        <NavLink to="/" className="topbar-brand">
          <span className="brand-mark" aria-hidden="true">
            LL
          </span>
          LabelLens
        </NavLink>
        <div className="topbar-status">
          {queue.count > 0 && <span className="queue-badge">{queue.count} offline</span>}
          <span className={`sync-dot${queue.online ? "" : " offline"}`} aria-hidden="true" />
        </div>
      </header>

      {drawerOpen && (
        <>
          <div className="drawer-backdrop" onClick={() => setDrawerOpen(false)} />
          <aside className="sidebar drawer-open">
            <Sidebar {...sidebarProps} onNavigate={() => setDrawerOpen(false)} onClose={() => setDrawerOpen(false)} />
          </aside>
        </>
      )}

      <div className="app-main">
        <main className="page">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route
              path="/inspect"
              element={<Capture officerName={officerName} setOfficerName={setOfficerName} />}
            />
            <Route path="/inspections" element={<Scans />} />
            <Route
              path="/inspections/:scanId"
              element={<ScanDetail officerName={officerName} />}
            />
            <Route path="/cases" element={<Cases />} />
            <Route path="/compliance" element={<Worklist />} />
            <Route path="/entities/:entityId" element={<Entity />} />
            <Route path="/evidence" element={<Ledger />} />
            <Route path="/reports" element={<Report />} />
            <Route
              path="/analytics"
              element={
                <Suspense fallback={<Loading />}>
                  <Analytics />
                </Suspense>
              }
            />
            <Route
              path="/settings"
              element={<Settings officerName={officerName} setOfficerName={setOfficerName} />}
            />
            <Route path="/rules" element={<Rules />} />
          </Routes>
        </main>
      </div>

      {location.pathname !== "/inspect" && (
        <NavLink to="/inspect" className="fab">
          <IconPlus size={16} />
          New inspection
        </NavLink>
      )}
    </div>
  );
}
