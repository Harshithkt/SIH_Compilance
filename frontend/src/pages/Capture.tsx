import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { ConfirmDialog, Steps } from "../components/common";
import { IconCamera, IconUpload } from "../components/icons";
import { useI18n } from "../i18n";
import { enqueue, useQueueStatus } from "../offlineQueue";
import type { QualityReport } from "../types";

export default function Capture() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const fileInput = useRef<HTMLInputElement>(null);
  const queue = useQueueStatus();

  const [product, setProduct] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [isFood, setIsFood] = useState(true);
  const [isImported, setIsImported] = useState(false);
  const [sourceType, setSourceType] = useState<"PHYSICAL_LABEL" | "ECOMMERCE_LISTING">("PHYSICAL_LABEL");
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [locating, setLocating] = useState(false);
  const [rawText, setRawText] = useState("");
  const [showOffline, setShowOffline] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [rejection, setRejection] = useState<QualityReport | null>(null);
  const [confirmAnyway, setConfirmAnyway] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<string>("");
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then((h) => setProvider(h.text_recognition_provider))
      .catch(() => setProvider(""));
  }, []);

  // The manual provider means no vision backend is reachable, so offline entry is the
  // only way to get declarations in — surface it rather than letting the scan come back empty.
  useEffect(() => {
    if (provider === "manual") setShowOffline(true);
  }, [provider]);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

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

  const pickFile = useCallback((f: File | null | undefined) => {
    if (!f) return;
    setFile(f);
    setRejection(null);
  }, []);

  async function submit(skipQualityGate = false) {
    if (!file) return;
    setSubmitting(true);
    setError(null);
    setRejection(null);

    const input = {
      image: file,
      lang,
      productName: product.trim() || undefined,
      gpsLat: coords?.lat,
      gpsLon: coords?.lon,
      isFoodItem: isFood,
      isImported: isImported,
      sourceType: sourceType,
      rawText: rawText.trim() || undefined,
      skipQualityGate,
    };

    try {
      const result = await api.createScan(input);
      navigate(`/inspections/${result.scan.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setRejection(err.detail as QualityReport);
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        // No response at all — the officer is out of signal. Hold the inspection
        // locally rather than losing the capture.
        await enqueue(input);
        await queue.refresh();
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

  const currentStep = submitting ? 1 : 0;

  return (
    <>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{t("capture.title")}</h1>
          <p>{t("capture.subtitle")}</p>
        </div>
      </div>

      <Steps current={currentStep} />

      {queue.count > 0 && (
        <div
          className="banner banner-warn row"
          style={{ justifyContent: "space-between", marginBottom: 16 }}
        >
          <span>
            <strong>
              {queue.count} inspection{queue.count === 1 ? "" : "s"} held on this device
            </strong>{" "}
            — captured without connectivity and not yet committed to the ledger.
          </span>
          <button className="btn btn-sm btn-primary" onClick={queue.sync} disabled={queue.syncing}>
            {queue.syncing ? "Syncing…" : "Sync now"}
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
          {/* The officer is no longer typed in — it comes from the signed-in account —
              but who the record will be attributed to still has to be visible before
              they commit a photograph as evidence. */}
          <div>
            <div
              style={{ fontSize: 12.5, fontWeight: 640, color: "var(--ink-2)", marginBottom: 5 }}
            >
              {t("capture.officer")}
            </div>
            <div className="row" style={{ gap: 8 }}>
              <strong>{user?.full_name}</strong>
              {user && <span className="role-pill">{t(`auth.role.${user.role}` as never)}</span>}
            </div>
          </div>

          <label className="field">
            {t("capture.product")}
            <input
              type="text"
              value={product}
              onChange={(e) => setProduct(e.target.value)}
              placeholder="Masala Namkeen 200g"
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
            <span style={{ fontSize: 13, fontWeight: 600 }}>Inspection Source</span>
            <div className="row" style={{ gap: 16, marginTop: 4 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                <input
                  type="radio"
                  name="sourceType"
                  value="PHYSICAL_LABEL"
                  checked={sourceType === "PHYSICAL_LABEL"}
                  onChange={() => setSourceType("PHYSICAL_LABEL")}
                />
                Physical Label Scan
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                <input
                  type="radio"
                  name="sourceType"
                  value="ECOMMERCE_LISTING"
                  checked={sourceType === "ECOMMERCE_LISTING"}
                  onChange={() => setSourceType("ECOMMERCE_LISTING")}
                />
                E-commerce Listing Screenshot
              </label>
            </div>
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
                <button className="btn btn-sm" onClick={() => setConfirmAnyway(true)} disabled={submitting}>
                  {t("capture.useAnyway")}
                </button>
              </div>
            </div>
          )}

          <button
            className="btn btn-primary btn-lg"
            onClick={() => submit(false)}
            disabled={!file || submitting}
          >
            <IconCamera size={16} />
            {submitting ? t("capture.submitting") : t("capture.submit")}
          </button>
        </div>

        <div className="stack">
          <div className="card card-pad">
            {preview ? (
              <div className="stack" style={{ gap: 10 }}>
                <div className="label-viewer" style={{ display: "block" }}>
                  <img src={preview} alt="Selected label" />
                </div>
                <button className="btn btn-sm btn-block" onClick={() => fileInput.current?.click()}>
                  {t("capture.change")}
                </button>
              </div>
            ) : (
              <div
                className={`dropzone${dragOver ? " drag" : ""}`}
                onClick={() => fileInput.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  pickFile(e.dataTransfer.files?.[0]);
                }}
                role="button"
                tabIndex={0}
              >
                <div className="dropzone-icon">
                  <IconUpload size={30} />
                </div>
                <h3>{t("capture.dropTitle")}</h3>
                <p>{t("capture.dropHint")}</p>
              </div>
            )}

            <input
              ref={fileInput}
              type="file"
              accept="image/*"
              capture="environment"
              style={{ display: "none" }}
              onChange={(e) => pickFile(e.target.files?.[0])}
            />

            {provider && (
              <p className="muted" style={{ marginBottom: 0, marginTop: 12, fontSize: 12.5 }}>
                Text recognition: <code>{provider}</code>
                {provider === "manual" &&
                  " — no vision backend configured, so type the declarations above."}
              </p>
            )}
          </div>
        </div>
      </div>

      {confirmAnyway && (
        <ConfirmDialog
          title={t("capture.confirmTitle")}
          body={t("capture.confirmBody")}
          confirmLabel={t("capture.useAnyway")}
          onConfirm={() => {
            setConfirmAnyway(false);
            submit(true);
          }}
          onCancel={() => setConfirmAnyway(false)}
        />
      )}
    </>
  );
}
