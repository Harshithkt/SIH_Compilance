import { useState, type FormEvent } from "react";
import { loginErrorMessage, useAuth } from "../auth";
import { IconLock, IconShieldCheck } from "../components/icons";
import { useI18n, type Lang } from "../i18n";

/** Shown in place of the whole application until an account is signed in — every
 *  inspection, correction and closure is attributed to the account that made it. */
export default function Login() {
  const { t, lang, setLang } = useI18n();
  const { login } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(loginErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-shell">
      <section className="auth-aside">
        <div className="auth-brand">
          <span className="brand-mark auth-brand-mark">LL</span>
          <div>
            <strong>{t("app.name")}</strong>
            <span>{t("app.tagline")}</span>
          </div>
        </div>

        <h2 className="auth-aside-title">
          Evidence-grade inspection, from the shop floor to the case file.
        </h2>

        <ul className="auth-points">
          <li>
            <IconShieldCheck size={16} />
            Deterministic LMPC rule packs — every verdict pinned to the version in force.
          </li>
          <li>
            <IconLock size={16} />
            Hash-chained evidence ledger, tamper-evident end to end.
          </li>
        </ul>

        <p className="auth-footnote">
          The officer makes the final legal decision. The system assists and records it.
        </p>
      </section>

      <section className="auth-main">
        <div className="auth-card">
          <div className="auth-card-head">
            <h1>{t("auth.title")}</h1>
            <p>{t("auth.subtitle")}</p>
          </div>

          <form className="stack" style={{ gap: 14 }} onSubmit={onSubmit}>
            <label className="field">
              {t("auth.username")}
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                required
              />
            </label>

            <label className="field">
              {t("auth.password")}
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>

            {error && <div className="banner banner-bad">{error}</div>}

            <button
              type="submit"
              className="btn btn-primary btn-lg btn-block"
              disabled={submitting || !username.trim() || !password}
            >
              {submitting ? t("auth.signingIn") : t("auth.signIn")}
            </button>
          </form>

          <div className="auth-demo">
            <span className="auth-demo-label">{t("auth.demoAccounts")}</span>
            <div className="auth-demo-rows">
              {(["officer", "supervisor", "admin"] as const).map((account) => (
                <button
                  key={account}
                  type="button"
                  className="auth-demo-row"
                  onClick={() => {
                    setUsername(account);
                    setPassword("labellens-demo");
                  }}
                >
                  <span className="mono">{account}</span>
                  <span className="muted">{t(`auth.role.${account}` as never)}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="auth-lang">
            {(["en", "hi"] as Lang[]).map((option) => (
              <button
                key={option}
                type="button"
                className={`btn btn-sm${lang === option ? " btn-dark" : ""}`}
                onClick={() => setLang(option)}
              >
                {option === "en" ? "English" : "हिन्दी"}
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
