import { useCallback, useState } from "react";

/** Officer identity is per-device, not per-account — there is no login. It is used to
 *  attribute new inspections and corrections, and is read by several pages, so it
 *  lives in one place rather than three separate `localStorage` reads. */
export const OFFICER_KEY = "labellens.officer";

export function useOfficerName() {
  const [name, setNameState] = useState(() => localStorage.getItem(OFFICER_KEY) ?? "");

  const setName = useCallback((next: string) => {
    localStorage.setItem(OFFICER_KEY, next.trim());
    setNameState(next.trim());
  }, []);

  return { name, setName };
}
