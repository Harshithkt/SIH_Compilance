import { useEffect, useState } from "react";
import { ApiError, api } from "../api";
import { useAuth, type AuthUser, type Role } from "../auth";
import { EmptyState, ErrorBanner, Loading, initials } from "../components/common";
import { IconUsers } from "../components/icons";
import { useI18n } from "../i18n";

const ROLES: Role[] = ["officer", "supervisor", "admin"];

/** Account administration — admin only. The API enforces that independently; this
 *  page exists so the capability is reachable at all. */
export default function Team() {
  const { t } = useI18n();
  const { user } = useAuth();

  const [accounts, setAccounts] = useState<AuthUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("officer");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function load() {
    setError(null);
    api
      .listUsers()
      .then(setAccounts)
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));
  }

  useEffect(load, []);

  async function createAccount() {
    setCreating(true);
    setFormError(null);
    try {
      await api.createUser({
        username: username.trim(),
        full_name: fullName.trim(),
        password,
        role,
      });
      setUsername("");
      setFullName("");
      setPassword("");
      setRole("officer");
      load();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : t("common.error"));
    } finally {
      setCreating(false);
    }
  }

  async function toggleActive(account: AuthUser) {
    setError(null);
    try {
      await api.setUserActive(account.username, !account.is_active);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("common.error"));
    }
  }

  return (
    <>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{t("team.title")}</h1>
          <p>{t("team.subtitle")}</p>
        </div>
      </div>

      {error && <ErrorBanner message={error} onRetry={load} />}

      <div className="stack">
        <div className="card">
          <div className="card-head">
            <h2>{t("team.title")}</h2>
            <span className="muted">{accounts?.length ?? ""}</span>
          </div>

          {!accounts ? (
            <Loading />
          ) : accounts.length === 0 ? (
            <EmptyState icon={<IconUsers size={18} />} title={t("team.empty")} />
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("team.account")}</th>
                    <th>{t("team.role")}</th>
                    <th>{t("team.status")}</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((account) => (
                    <tr key={account.id}>
                      <td>
                        <div className="row" style={{ gap: 10, flexWrap: "nowrap" }}>
                          <span
                            className="officer-avatar"
                            style={{ width: 28, height: 28, fontSize: 11 }}
                          >
                            {initials(account.full_name)}
                          </span>
                          <span style={{ minWidth: 0 }}>
                            <strong style={{ display: "block", fontSize: 13 }}>
                              {account.full_name}
                            </strong>
                            <span className="mono muted">{account.username}</span>
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className="role-pill">
                          {t(`auth.role.${account.role}` as never)}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`badge ${account.is_active ? "badge-good" : "badge-muted"}`}
                        >
                          {account.is_active ? t("team.active") : t("team.inactive")}
                        </span>
                      </td>
                      <td>
                        {account.username === user?.username ? (
                          <span className="muted" style={{ fontSize: 12 }}>
                            {t("team.you")}
                          </span>
                        ) : (
                          <button
                            className={`btn btn-sm${account.is_active ? " btn-danger" : ""}`}
                            onClick={() => toggleActive(account)}
                          >
                            {account.is_active ? t("team.deactivate") : t("team.activate")}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card card-pad">
          <h2 style={{ marginBottom: 14 }}>{t("team.newAccount")}</h2>
          <div className="stack" style={{ gap: 12, maxWidth: 360 }}>
            <label className="field">
              {t("team.username")}
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="off"
              />
            </label>
            <label className="field">
              {t("team.fullName")}
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Insp. M. Nair"
                autoComplete="off"
              />
            </label>
            <label className="field">
              {t("team.password")}
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
            </label>
            <label className="field">
              {t("team.role")}
              <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
                {ROLES.map((option) => (
                  <option key={option} value={option}>
                    {t(`auth.role.${option}` as never)}
                  </option>
                ))}
              </select>
            </label>

            {formError && <div className="banner banner-bad">{formError}</div>}

            <div>
              <button
                className="btn btn-primary btn-sm"
                onClick={createAccount}
                disabled={
                  creating || !username.trim() || !fullName.trim() || password.length < 8
                }
              >
                {creating ? t("team.creating") : t("team.create")}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
