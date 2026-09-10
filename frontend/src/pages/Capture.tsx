import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { useI18n } from "../i18n";
import { enqueue, flush, listQueued } from "../offlineQueue";
import type { QualityReport } from "../types";

const OFFICER_KEY = "labellens.officer";

export default function Capture() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const fileInput = useRef<HTMLInputElement>(null);

  const [officer, setOfficer] = useState(() => localStorage.getItem(OFFICER_KEY) ?? "");
  const [product, setProduct] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [isFood, setIsFood] = useState(true);
  const [isImported, setIsImported] = useState(false);
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [locating, setLocating] = useState(false);
  const [rawText, setRawText] = useState("");
  const [showOffline, setShowOffline] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [rejection, setRejection] = useState<QualityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<string>("");
  const [queuedCount, setQueuedCount] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshQueue = useCallback(async () => {
    setQueuedCount((await listQueued()).length);
  }, []);

  const syncQueue = useCallback(async () => {
    setSyncing(true);
    try {
      const result = await flush();
      if (result.sent || result.failed) {
        setNotice(
          `Synced ${result.sent} queued inspection${result.sent === 1 ? "" : "s"}` +
            (result.failed ? `; ${result.failed} rejected by the server.` : "."),
        );
      }
    } finally {
      setSyncing(false);
      refreshQueue();
    }
  }, [refreshQueue]);

  useEffect(() => {
    api
      .health()
      .then((h) => setProvider(h.text_recognition_provider))
      .catch(() => setProvider(""));
    refreshQueue();
  }, [refreshQueue]);

  useEffect(() => {
    window.addEventListener("online", syncQueue);
    return () => window.removeEventListener("online", syncQueue);
  }, [syncQueue]);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // The manual provider means no vision backend is reachable, so offline entry is the
  // only way to get declarations in — surface it rather than letting the scan come back empty.
  useEffect(() => {
    if (provider === "manual") setShowOffline(true);
  }, [provider]);

  function locate() {
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setLocating(false);
      },
      () => setLocating(false),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  async function submit(skipQualityGate = false) {
    if (!file || !officer.trim()) return;
    setSubmitting(true);
    setError(null);
    setRejection(null);
    localStorage.setItem(OFFICER_KEY, officer.trim());

    const input = {
      image: file,
      officerName: officer.trim(),
      lang,
      productName: product.trim() || undefined,
      gpsLat: coords?.lat,
      gpsLon: coords?.lon,
      isFoodItem: isFood,
      isImported: isImported,
      rawText: rawText.trim() || undefined,
      skipQualityGate,
    };

    try {
      const result = await api.createScan(input);
      navigate(`/scans/${result.scan.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setRejection(err.detail as QualityReport);
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        // No response at all — the officer is out of signal. Hold the inspection
        // locally rather than losing the capture.
        await enqueue(input);
        await refreshQueue();
        setFile(null);
        setProduct("");
        setNotice(
          "No connectivity. This inspection is held on the device and will be submitted when you are back online.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>{t("capture.title")}</h1>
        <p>{t("capture.subtitle")}</p>
      </div>

      {queuedCount > 0 && (
        <div
          className="banner banner-warn row"
          style={{ justifyContent: "space-between", marginBottom: 16 }}
        >
          <span>
            <strong>
              {queuedCount} inspection{queuedCount === 1 ? "" : "s"} held on this device
            </strong>{" "}
            — captured without connectivity and not yet committed to the ledger.
          </span>
          <button className="btn btn-sm btn-primary" onClick={syncQueue} disabled={syncing}>
            {syncing ? "Syncing…" : "Sync now"}
          </button>
        </div>
      )}

      {notice && (
        <div
          className="banner banner-info row"
          style={{ justifyContent: "space-between", marginBottom: 16 }}
        >
          <span>{notice}</span>
          <button className="btn btn-sm" onClick={() => setNotice(null)}>
            {t("common.close")}
          </button>
        </div>
      )}

      <div className="split">
        <div className="card card-pad stack">
          <label className="field">
            {t("capture.officer")}
            <input
              type="text"
              value={officer}
              onChange={(e) => setOfficer(e.target.value)}
              placeholder="Insp. R. Sharma"
            />
          </label>

          <label className="field">
            {t("capture.product")}
            <input
              type="text"
              value={product}
              onChange={(e) => setProduct(e.target.value)}
              placeholder="Masala Namkeen 200g"
            />
          </label>

          <label className="field">
            {t("capture.photo")}
            <input
              ref={fileInput}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setRejection(null);
              }}
            />
          </label>

          <div className="row" style={{ gap: 18 }}>
            <label className="checkbox">
              <input type="checkbox" checked={isFood} onChange={(e) => setIsFood(e.target.checked)} />
              {t("capture.food")}
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={isImported}
                onChange={(e) => setIsImported(e.target.checked)}
              />
              {t("capture.imported")}
            </label>
          </div>

          <div className="field">
            {t("capture.location")}
            <div className="row">
              <button className="btn btn-sm" onClick={locate} disabled={locating}>
                {locating ? t("capture.locating") : t("capture.locate")}
              </button>
              {coords && (
                <span className="mono muted">
                  {coords.lat.toFixed(5)}, {coords.lon.toFixed(5)}
                </span>
              )}
            </div>
          </div>

          <div>
            <button
              className="btn btn-sm"
              onClick={() => setShowOffline((v) => !v)}
              style={{ marginBottom: showOffline ? 8 : 0 }}
            >
              {showOffline ? "− " : "+ "}
              {t("capture.rawText")}
            </button>
            {showOffline && (
              <>
                <p className="muted" style={{ margin: "0 0 8px", fontSize: 12.5 }}>
                  {t("capture.rawTextHelp")}
                </p>
                <textarea
                  rows={7}
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  placeholder={
                    "Common Name: Namkeen Mixture\nManufactured by: Sunrise Foods Pvt Ltd, Pune 411026\nNet Quantity: 200 g\nMRP: Rs. 45.00\nMfg Date: 07/2026\nConsumer Care: care@example.in\nFSSAI Lic No: 11522998000123"
                  }
                />
              </>
            )}
          </div>

          {error && <div className="banner banner-bad">{error}</div>}

          {rejection && (
            <div className="banner banner-warn stack" style={{ gap: 10 }}>
              <strong>{t("capture.rejected")}</strong>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {rejection.issues?.map((issue) => (
                  <li key={issue.code}>
                    {issue.message} <em>{issue.guidance}</em>
                  </li>
                ))}
              </ul>
              <div className="row">
                <button
                  className="btn btn-sm btn-primary"
                  onClick={() => {
                    setFile(null);
                    setRejection(null);
                    fileInput.current?.click();
                  }}
                >
                  {t("capture.retake")}
                </button>
                <button className="btn btn-sm" onClick={() => submit(true)} disabled={submitting}>
                  {t("capture.useAnyway")}
                </button>
              </div>
            </div>
          )}

          <button
            className="btn btn-primary"
            onClick={() => submit(false)}
            disabled={!file || !officer.trim() || submitting}
          >
            {submitting ? t("capture.submitting") : t("capture.submit")}
          </button>
        </div>

        <div className="card card-pad">
          {preview ? (
            <img
              src={preview}
              alt="Selected label"
              style={{ maxWidth: "100%", borderRadius: 6, display: "block" }}
            />
          ) : (
            <div className="empty">{t("capture.photo")}</div>
          )}

          {provider && (
            <p className="muted" style={{ marginBottom: 0, fontSize: 12.5 }}>
              Text recognition: <code>{provider}</code>
              {provider === "manual" &&
                " — no vision backend configured, so type the declarations above."}
            </p>
          )}
        </div>
      </div>
    </>
  );
}
