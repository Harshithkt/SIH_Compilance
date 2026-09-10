import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type Lang = "en" | "hi";

const STRINGS = {
  en: {
    "app.name": "LabelLens",
    "app.tagline": "Enforcement case-file for Legal Metrology",
    "nav.capture": "Inspect",
    "nav.worklist": "Worklist",
    "nav.scans": "Inspections",
    "nav.ledger": "Evidence ledger",
    "nav.rules": "Rule packs",
    "nav.report": "Monthly report",

    "capture.title": "New inspection",
    "capture.subtitle":
      "Photograph the declaration panel. The frame is checked for focus, glare and contrast before it is accepted as evidence.",
    "capture.officer": "Inspecting officer",
    "capture.product": "Commodity (optional)",
    "capture.photo": "Label photograph",
    "capture.food": "Food item (FSSAI licence required)",
    "capture.imported": "Imported package",
    "capture.location": "Capture location",
    "capture.locate": "Use my location",
    "capture.locating": "Getting location…",
    "capture.submit": "Run inspection",
    "capture.submitting": "Reading label…",
    "capture.rawText": "Typed declarations (offline entry)",
    "capture.rawTextHelp":
      "Use when there is no connectivity for the vision model — type what is printed, one declaration per line.",
    "capture.retake": "Retake photograph",
    "capture.useAnyway": "Use anyway (recorded)",
    "capture.rejected": "Frame rejected by the capture-quality gate",

    "verdict.GO": "COMPLIANT",
    "verdict.FIX": "MINOR FIXES",
    "verdict.REVIEW": "FOR ACTION",
    "verdict.PENDING": "PENDING",

    "scan.declarations": "Declarations",
    "scan.violations": "Contraventions",
    "scan.evidence": "Evidence",
    "scan.docket": "Download evidence docket",
    "scan.field": "Declaration",
    "scan.value": "Value read",
    "scan.status": "Status",
    "scan.clause": "Clause",
    "scan.finding": "Finding",
    "scan.severity": "Severity",
    "scan.explain": "Explain in plain language",
    "scan.noViolations": "No contravention of the checked provisions was found.",
    "scan.rulePinned": "Rules applied",
    "scan.compareRules": "Compare against",
    "scan.ledgerEntry": "Ledger entry",
    "scan.imageHash": "Image SHA-256",
    "scan.capturedAt": "Captured",
    "scan.officer": "Officer",
    "scan.gps": "Location",

    "worklist.title": "Enforcement worklist",
    "worklist.subtitle":
      "Ranked by severity-weighted risk and repeat contraventions, so the worst offenders surface first.",
    "worklist.entity": "Manufacturer / packer / importer",
    "worklist.risk": "Risk",
    "worklist.scans": "Scans",
    "worklist.violations": "Findings",
    "worklist.repeat": "Repeat offender",
    "worklist.clauses": "Most-breached clauses",
    "worklist.empty": "No inspections recorded yet.",

    "ledger.title": "Evidence ledger",
    "ledger.subtitle":
      "Every inspection is committed as a hash-chained entry covering the record and the photograph. Verification recomputes the whole chain.",
    "ledger.verify": "Verify chain",
    "ledger.verifying": "Recomputing chain…",
    "ledger.entry": "Entry",
    "ledger.scan": "Inspection",
    "ledger.hash": "Entry hash",

    "report.title": "Monthly compliance report",
    "report.subtitle":
      "Inspection activity for the period, drawn from committed ledger records and reported with the integrity status of the chain behind them.",
    "report.inspections": "Inspections",
    "report.rate": "Non-compliance",
    "report.entities": "Entities with findings",
    "report.clauses": "Contraventions by clause",
    "report.priority": "Priority entities",
    "report.officers": "Inspections by officer",
    "report.versions": "Rule versions applied",
    "report.raw": "Open raw data",

    "rules.title": "Rule packs",
    "rules.subtitle":
      "Clause-by-clause encoding of the LMPC Rules, 2011. Every verdict is pinned to the version in force on the inspection date.",
    "rules.active": "Active",
    "rules.effective": "In force from",
    "rules.count": "Clauses",

    "scans.title": "Inspections",
    "scans.subtitle": "Searchable history of every inspection recorded on this device.",
    "scans.search": "Search by commodity",
    "scans.all": "All verdicts",
    "common.loading": "Loading…",
    "common.error": "Something went wrong",
    "common.retry": "Retry",
    "common.back": "Back",
    "common.close": "Close",
  },
  hi: {
    "app.name": "लेबललेंस",
    "app.tagline": "विधिक माप विज्ञान हेतु प्रवर्तन प्रकरण-पत्रावली",
    "nav.capture": "निरीक्षण",
    "nav.worklist": "कार्यसूची",
    "nav.scans": "निरीक्षण अभिलेख",
    "nav.ledger": "साक्ष्य बही",
    "nav.rules": "नियम संस्करण",
    "nav.report": "मासिक प्रतिवेदन",

    "capture.title": "नया निरीक्षण",
    "capture.subtitle":
      "घोषणा पटल का चित्र लें। साक्ष्य के रूप में स्वीकार करने से पूर्व फ्रेम की स्पष्टता, चमक और कंट्रास्ट जाँची जाती है।",
    "capture.officer": "निरीक्षक अधिकारी",
    "capture.product": "वस्तु (वैकल्पिक)",
    "capture.photo": "लेबल का चित्र",
    "capture.food": "खाद्य वस्तु (एफएसएसएआई लाइसेंस आवश्यक)",
    "capture.imported": "आयातित पैकेज",
    "capture.location": "स्थान",
    "capture.locate": "मेरा स्थान लें",
    "capture.locating": "स्थान प्राप्त किया जा रहा है…",
    "capture.submit": "निरीक्षण करें",
    "capture.submitting": "लेबल पढ़ा जा रहा है…",
    "capture.rawText": "टंकित घोषणाएँ (ऑफ़लाइन प्रविष्टि)",
    "capture.rawTextHelp":
      "जब नेटवर्क उपलब्ध न हो तब उपयोग करें — पैक पर मुद्रित प्रत्येक घोषणा एक पंक्ति में लिखें।",
    "capture.retake": "पुनः चित्र लें",
    "capture.useAnyway": "फिर भी उपयोग करें (अभिलिखित)",
    "capture.rejected": "गुणवत्ता जाँच द्वारा चित्र अस्वीकृत",

    "verdict.GO": "अनुपालन",
    "verdict.FIX": "सुधार अपेक्षित",
    "verdict.REVIEW": "कार्रवाई हेतु",
    "verdict.PENDING": "लंबित",

    "scan.declarations": "घोषणाएँ",
    "scan.violations": "उल्लंघन",
    "scan.evidence": "साक्ष्य",
    "scan.docket": "साक्ष्य पत्रावली डाउनलोड करें",
    "scan.field": "घोषणा",
    "scan.value": "पढ़ा गया मान",
    "scan.status": "स्थिति",
    "scan.clause": "नियम",
    "scan.finding": "निष्कर्ष",
    "scan.severity": "गंभीरता",
    "scan.explain": "सरल भाषा में समझाएँ",
    "scan.noViolations": "जाँचे गए प्रावधानों का कोई उल्लंघन नहीं मिला।",
    "scan.rulePinned": "लागू नियम",
    "scan.compareRules": "इससे तुलना करें",
    "scan.ledgerEntry": "बही प्रविष्टि",
    "scan.imageHash": "चित्र SHA-256",
    "scan.capturedAt": "चित्रण समय",
    "scan.officer": "अधिकारी",
    "scan.gps": "स्थान",

    "worklist.title": "प्रवर्तन कार्यसूची",
    "worklist.subtitle":
      "गंभीरता एवं पुनरावृत्ति के आधार पर क्रमित, जिससे सर्वाधिक उल्लंघनकर्ता सबसे ऊपर आएँ।",
    "worklist.entity": "निर्माता / पैकर / आयातक",
    "worklist.risk": "जोखिम",
    "worklist.scans": "निरीक्षण",
    "worklist.violations": "निष्कर्ष",
    "worklist.repeat": "पुनरावृत्त उल्लंघनकर्ता",
    "worklist.clauses": "सर्वाधिक उल्लंघित नियम",
    "worklist.empty": "अभी तक कोई निरीक्षण अभिलिखित नहीं।",

    "ledger.title": "साक्ष्य बही",
    "ledger.subtitle":
      "प्रत्येक निरीक्षण अभिलेख और चित्र सहित हैश-श्रृंखलित प्रविष्टि के रूप में दर्ज होता है। सत्यापन पूरी श्रृंखला की पुनर्गणना करता है।",
    "ledger.verify": "श्रृंखला सत्यापित करें",
    "ledger.verifying": "श्रृंखला की पुनर्गणना…",
    "ledger.entry": "प्रविष्टि",
    "ledger.scan": "निरीक्षण",
    "ledger.hash": "प्रविष्टि हैश",

    "report.title": "मासिक अनुपालन प्रतिवेदन",
    "report.subtitle":
      "अवधि की निरीक्षण गतिविधि, बही में दर्ज अभिलेखों से संकलित तथा श्रृंखला की अखंडता स्थिति सहित।",
    "report.inspections": "निरीक्षण",
    "report.rate": "अननुपालन दर",
    "report.entities": "उल्लंघनकर्ता इकाइयाँ",
    "report.clauses": "नियमानुसार उल्लंघन",
    "report.priority": "प्राथमिकता इकाइयाँ",
    "report.officers": "अधिकारीवार निरीक्षण",
    "report.versions": "लागू नियम संस्करण",
    "report.raw": "मूल आँकड़े खोलें",

    "rules.title": "नियम संस्करण",
    "rules.subtitle":
      "एलएमपीसी नियम, 2011 का नियमवार अंकन। प्रत्येक निर्णय निरीक्षण तिथि पर प्रवृत्त संस्करण से जुड़ा रहता है।",
    "rules.active": "सक्रिय",
    "rules.effective": "प्रवृत्त तिथि",
    "rules.count": "नियम",

    "scans.title": "निरीक्षण अभिलेख",
    "scans.subtitle": "इस उपकरण पर दर्ज प्रत्येक निरीक्षण का खोजयोग्य अभिलेख।",
    "scans.search": "वस्तु द्वारा खोजें",
    "scans.all": "सभी निर्णय",
    "common.loading": "लोड हो रहा है…",
    "common.error": "कुछ त्रुटि हुई",
    "common.retry": "पुनः प्रयास",
    "common.back": "वापस",
    "common.close": "बंद करें",
  },
} as const;

type Key = keyof (typeof STRINGS)["en"];

interface I18nValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: Key) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const stored = localStorage.getItem("labellens.lang");
    return stored === "hi" ? "hi" : "en";
  });

  const value = useMemo<I18nValue>(
    () => ({
      lang,
      setLang: (next) => {
        localStorage.setItem("labellens.lang", next);
        setLangState(next);
      },
      t: (key) => STRINGS[lang][key] ?? STRINGS.en[key] ?? key,
    }),
    [lang],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside I18nProvider");
  return ctx;
}

export const FIELD_LABELS: Record<string, { en: string; hi: string }> = {
  mrp: { en: "Retail sale price (MRP)", hi: "अधिकतम खुदरा मूल्य" },
  net_quantity: { en: "Net quantity", hi: "शुद्ध मात्रा" },
  mfg_date: { en: "Month & year of manufacture", hi: "निर्माण माह/वर्ष" },
  manufacturer_details: { en: "Manufacturer / packer / importer", hi: "निर्माता / पैकर / आयातक" },
  consumer_care: { en: "Consumer care details", hi: "उपभोक्ता सेवा विवरण" },
  country_of_origin: { en: "Country of origin", hi: "उत्पत्ति देश" },
  fssai_license_no: { en: "FSSAI licence number", hi: "एफएसएसएआई लाइसेंस संख्या" },
  common_name: { en: "Common / generic name", hi: "सामान्य नाम" },
  best_before: { en: "Best before / use by", hi: "सर्वोत्तम उपयोग तिथि" },
  unit_price_sanity: { en: "Unit price check", hi: "इकाई मूल्य जाँच" },
};

export function fieldLabel(field: string, lang: Lang): string {
  return FIELD_LABELS[field]?.[lang] ?? field.replace(/_/g, " ");
}
