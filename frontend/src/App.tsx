import { NavLink, Route, Routes } from "react-router-dom";
import { useI18n } from "./i18n";
import Capture from "./pages/Capture";
import Entity from "./pages/Entity";
import Ledger from "./pages/Ledger";
import Rules from "./pages/Rules";
import ScanDetail from "./pages/ScanDetail";
import Scans from "./pages/Scans";
import Worklist from "./pages/Worklist";

export default function App() {
  const { t, lang, setLang } = useI18n();

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand">
            {t("app.name")}
            <small>{t("app.tagline")}</small>
          </NavLink>

          <nav className="nav">
            <NavLink to="/" end>
              {t("nav.capture")}
            </NavLink>
            <NavLink to="/worklist">{t("nav.worklist")}</NavLink>
            <NavLink to="/scans">{t("nav.scans")}</NavLink>
            <NavLink to="/ledger">{t("nav.ledger")}</NavLink>
            <NavLink to="/rules">{t("nav.rules")}</NavLink>
          </nav>

          <div className="lang-toggle">
            <button aria-pressed={lang === "en"} onClick={() => setLang("en")}>
              EN
            </button>
            <button aria-pressed={lang === "hi"} onClick={() => setLang("hi")}>
              हिं
            </button>
          </div>
        </div>
      </header>

      <main className="page">
        <Routes>
          <Route path="/" element={<Capture />} />
          <Route path="/worklist" element={<Worklist />} />
          <Route path="/entities/:entityId" element={<Entity />} />
          <Route path="/scans" element={<Scans />} />
          <Route path="/scans/:scanId" element={<ScanDetail />} />
          <Route path="/ledger" element={<Ledger />} />
          <Route path="/rules" element={<Rules />} />
        </Routes>
      </main>
    </div>
  );
}
