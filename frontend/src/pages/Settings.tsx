import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { initials } from "../components/common";
import { useI18n } from "../i18n";

export default function Settings() {
  const { t, lang, setLang } = useI18n();
  const { user, logout } = useAuth();

  const [health, setHealth] = useState<{
    active_rule_version: string;
    text_recognition_provider: string;
  } | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [changing, setChanging] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [changed, setChanged] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  async function changePassword() {
    setChanging(true);
    setPasswordError(null);
    setChanged(false);
    try {
      await api.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setChanged(true);
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : t("common.error"));
    } finally {
      setChanging(false);
    }
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
            <span
              className="officer-avatar"
              style={{ background: "var(--charcoal)", width: 42, height: 42, fontSize: 15 }}
            >
              {initials(user?.full_name ?? "?")}
            </span>
            <div>
              <h2>{user?.full_name}</h2>
              <div className="row" style={{ gap: 8, marginTop: 4 }}>
                <span className="mono muted">{user?.username}</span>
                {user && (
                  <span className="role-pill">{t(`auth.role.${user.role}` as never)}</span>
                )}
              </div>
            </div>
          </div>
          <p className="muted" style={{ fontSize: 12.5, marginTop: 0 }}>
            {t("settings.officerHelp")}
          </p>
          <button className="btn btn-sm" onClick={logout}>
            {t("auth.signOut")}
          </button>
        </div>

        <div className="card card-pad">
          <h2 style={{ marginBottom: 12 }}>{t("settings.password")}</h2>
          <div className="stack" style={{ gap: 12, maxWidth: 340 }}>
            <label className="field">
              {t("settings.currentPassword")}
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
              />
            </label>
            <label className="field">
              {t("settings.newPassword")}
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
              />
            </label>
            {passwordError && <div className="banner banner-bad">{passwordError}</div>}
            <div className="row">
              <button
                className="btn btn-sm btn-primary"
                onClick={changePassword}
                disabled={changing || !currentPassword || newPassword.length < 8}
              >
                {t("settings.changePassword")}
              </button>
              {changed && (
                <span className="muted" style={{ fontSize: 12.5 }}>
                  ✓ {t("settings.saved")}
                </span>
              )}
            </div>
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
            <dd>
              {health ? (
                <code>{health.text_recognition_provider}</code>
              ) : (
                <span className="muted">—</span>
              )}
            </dd>
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
