import type { ReactNode, SVGProps } from "react";

/** Small, dependency-free line icons in one consistent stroke style (24x24 grid,
 *  1.8px stroke, rounded caps/joins). Kept to exactly the set the shell and pages
 *  use — no icon library, so the bundle stays small and the field app stays fast
 *  to load over poor connectivity. */

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 18, children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export function IconDashboard(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="3.5" y="3.5" width="7.2" height="7.2" rx="1.2" />
      <rect x="13.3" y="3.5" width="7.2" height="4.6" rx="1.2" />
      <rect x="13.3" y="10.4" width="7.2" height="10.1" rx="1.2" />
      <rect x="3.5" y="13" width="7.2" height="7.5" rx="1.2" />
    </Svg>
  );
}

export function IconCamera(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 8.3c0-.9.7-1.6 1.6-1.6h1.8l1-1.7h7.2l1 1.7h1.8c.9 0 1.6.7 1.6 1.6v9.1c0 .9-.7 1.6-1.6 1.6H5.6C4.7 19 4 18.3 4 17.4z" />
      <circle cx="12" cy="12.8" r="3.4" />
    </Svg>
  );
}

export function IconList(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="4.6" cy="6" r="1" fill="currentColor" stroke="none" />
      <circle cx="4.6" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="4.6" cy="18" r="1" fill="currentColor" stroke="none" />
      <path d="M9 6h11M9 12h11M9 18h11" />
    </Svg>
  );
}

export function IconShieldCheck(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 3.4 5 5.9v5.6c0 4.6 3 7.9 7 9.1 4-1.2 7-4.5 7-9.1V5.9z" />
      <path d="m9 12 2.1 2.1L15.5 9.6" />
    </Svg>
  );
}

export function IconLock(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="5" y="10.5" width="14" height="9.5" rx="1.6" />
      <path d="M7.5 10.5V7.8a4.5 4.5 0 1 1 9 0v2.7" />
    </Svg>
  );
}

export function IconFileText(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M7 3.5h7.2L19 8.3V19a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 7 19z" />
      <path d="M14 3.5V8h4.6" />
      <path d="M9.6 12.5h5M9.6 15.7h5" />
    </Svg>
  );
}

export function IconBarChart(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 20V10M10 20V4M16 20v-7M4 20h16" />
    </Svg>
  );
}

export function IconSliders(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5 6h5M14 6h5M5 12h9M18 12h1M5 18h1M10 18h9" />
      <circle cx="12" cy="6" r="2" fill="var(--surface,#fff)" />
      <circle cx="16" cy="12" r="2" fill="var(--surface,#fff)" />
      <circle cx="8" cy="18" r="2" fill="var(--surface,#fff)" />
    </Svg>
  );
}

export function IconMenu(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 6.5h16M4 12h16M4 17.5h16" />
    </Svg>
  );
}

export function IconClose(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  );
}

export function IconCheckCircle(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.3 12.3 2.4 2.4 5-5.2" />
    </Svg>
  );
}

export function IconXCircle(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m9 9 6 6M15 9l-6 6" />
    </Svg>
  );
}

export function IconAlertTriangle(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 4.2 21 19.5H3z" />
      <path d="M12 10v4M12 16.6h.01" />
    </Svg>
  );
}

export function IconHelpCircle(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M9.6 9.5a2.4 2.4 0 1 1 3.4 2.2c-.8.4-1 1-1 1.8" />
      <path d="M12 16.6h.01" />
    </Svg>
  );
}

export function IconSearch(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="10.8" cy="10.8" r="6.3" />
      <path d="m20 20-4.4-4.4" />
    </Svg>
  );
}

export function IconMapPin(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 21s7-6.3 7-11.6A7 7 0 0 0 5 9.4C5 14.7 12 21 12 21Z" />
      <circle cx="12" cy="9.4" r="2.3" />
    </Svg>
  );
}

export function IconChevronRight(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m9 5 7 7-7 7" />
    </Svg>
  );
}

export function IconUpload(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 15.5V4M8 8l4-4 4 4" />
      <path d="M5 15.5v3a1.5 1.5 0 0 0 1.5 1.5h11a1.5 1.5 0 0 0 1.5-1.5v-3" />
    </Svg>
  );
}

export function IconPlus(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  );
}

export function IconRefresh(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M20 11a8 8 0 0 0-14.6-4.5M4 13a8 8 0 0 0 14.6 4.5" />
      <path d="M5.4 4v3.6H9M18.6 20v-3.6H15" />
    </Svg>
  );
}

export function IconZoomIn(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M10.5 7.7v5.6M7.7 10.5h5.6M20 20l-4.3-4.3" />
    </Svg>
  );
}

export function IconZoomOut(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M7.7 10.5h5.6M20 20l-4.3-4.3" />
    </Svg>
  );
}

export function IconRotate(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 10a8 8 0 0 1 14.6-4.5" />
      <path d="M20 4v4.5h-4.5" />
      <path d="M20 14a8 8 0 0 1-14.6 4.5" />
      <path d="M4 20v-4.5h4.5" />
    </Svg>
  );
}

export function IconImage(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="3.5" y="4.5" width="17" height="15" rx="1.6" />
      <circle cx="9" cy="9.6" r="1.6" />
      <path d="m5 18 5-5.3 3 2.7 3-3.3 3.5 3.4" />
    </Svg>
  );
}

export function IconLink(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M9.5 14.5 14.5 9.5" />
      <path d="M11 7.5 13 5.6a3.3 3.3 0 0 1 4.7 4.7L15.8 12" />
      <path d="M13 16.5 11 18.4a3.3 3.3 0 0 1-4.7-4.7L8.2 12" />
    </Svg>
  );
}

export function IconClock(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </Svg>
  );
}

export function IconArrowRight(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 12h15M13 6l6 6-6 6" />
    </Svg>
  );
}

export function IconPrinter(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M7 8.5V4h10v4.5" />
      <rect x="4" y="8.5" width="16" height="8" rx="1.4" />
      <path d="M7 15.5h10V20H7z" />
    </Svg>
  );
}

export function IconFolder(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 7.2c0-.9.7-1.6 1.6-1.6h4l1.8 2.1h7c.9 0 1.6.7 1.6 1.6v8.5c0 .9-.7 1.6-1.6 1.6H5.6C4.7 19.4 4 18.7 4 17.8z" />
    </Svg>
  );
}

export function IconDownload(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 4v11.5M8 12l4 4 4-4" />
      <path d="M5 17v3h14v-3" />
    </Svg>
  );
}

export function IconUsers(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3.5 19.5v-1.2a4 4 0 0 1 4-4h3a4 4 0 0 1 4 4v1.2" />
      <path d="M16.2 5.3a3.2 3.2 0 0 1 0 5.9" />
      <path d="M17.5 14.4a4 4 0 0 1 3 3.9v1.2" />
    </Svg>
  );
}
