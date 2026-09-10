import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { initials } from "../components/common";
import { useI18n } from "../i18n";

interface SettingsProps {
  officerName: string;
  setOfficerName: (name: string) => void;
}

export default function Settings({ officerName, setOfficerName }: SettingsProps) {
  const { t, lang, setLang } = useI18n();
  const [draft, setDraft] = useState(officerName);
  const [saved, setSaved] = useState(false);
  const [health, setHealth] = useState<{ active_rule_version: string; text_recognition_provider: string } | null>(
    null,
  );

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  function save() {
    setOfficerName(draft);
    setSaved(true);
    setTimeout(() => setSaved(false), 1800);
  }

  return (
    <>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{t("settings.title")}</h1>
          <p>{t("settings.subtitle")}</p>
        </div>
      </div>

      <div className="stack">
        <div className="card card-pad">
          <div className="row" style={{ gap: 12, marginBottom: 14 }}>
            <span className="officer-avatar" style={{ background: "var(--charcoal)", width: 40, height: 40, fontSize: 14 }}>
              {initials(officerName || "?")}
            </span>
            <h2>{t("settings.officer")}</h2>
          </div>
          <label className="field" style={{ maxWidth: 340 }}>
            {t("settings.officerName")}
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Insp. R. Sharma"
            />
          </label>
          <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
            {t("settings.officerHelp")}
          </p>
          <div className="row" style={{ marginTop: 10 }}>
            <button className="btn btn-primary btn-sm" onClick={save} disabled={!draft.trim()}>
              Save
            </button>
            {saved && <span className="muted" style={{ fontSize: 12.5 }}>✓ {t("settings.saved")}</span>}
          </div>
        </div>

        <div className="card card-pad">
          <h2 style={{ marginBottom: 12 }}>{t("settings.language")}</h2>
          <div className="row">
            <button
              className={`btn btn-sm${lang === "en" ? " btn-primary" : ""}`}
              onClick={() => setLang("en")}
            >
              English
            </button>
            <button
              className={`btn btn-sm${lang === "hi" ? " btn-primary" : ""}`}
              onClick={() => setLang("hi")}
            >
              हिन्दी
            </button>
          </div>
        </div>

        <div className="card card-pad">
          <h2 style={{ marginBottom: 12 }}>{t("settings.system")}</h2>
          <dl className="dl">
            <dt>{t("settings.rulePack")}</dt>
            <dd>
              {health ? (
                <span className="mono">{health.active_rule_version}</span>
              ) : (
                <span className="muted">—</span>
              )}
            </dd>
            <dt>{t("settings.provider")}</dt>
            <dd>{health ? <code>{health.text_recognition_provider}</code> : <span className="muted">—</span>}</dd>
          </dl>
          <div style={{ marginTop: 12 }}>
            <Link to="/rules" className="btn btn-sm">
              {t("settings.viewRules")}
            </Link>
          </div>
        </div>
      </div>
    </>
  );
}
