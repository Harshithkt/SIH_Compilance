/* Offline inspection queue.
 *
 * A submission is only ever sent once, deliberately: each one is committed to the
 * hash-chained evidence ledger, so an automatic background retry that duplicated a POST
 * would put two ledger entries in for a single inspection. Queued inspections are held
 * in IndexedDB (the photograph is a Blob, too large for localStorage) and are flushed
 * one at a time when the officer is back online.
 */

import { useCallback, useEffect, useState } from "react";
import { api, type CaptureInput } from "./api";

const DB_NAME = "labellens";
const STORE = "pending-inspections";

export interface QueuedInspection {
  id: string;
  queuedAt: number;
  input: Omit<CaptureInput, "image">;
  image: Blob;
  imageName: string;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function tx<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return openDb().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const request = run(db.transaction(STORE, mode).objectStore(STORE));
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      }),
  );
}

export async function enqueue(input: CaptureInput): Promise<QueuedInspection> {
  const { image, ...rest } = input;
  const entry: QueuedInspection = {
    id: crypto.randomUUID(),
    queuedAt: Date.now(),
    input: rest,
    image,
    imageName: image.name || "capture.jpg",
  };
  await tx("readwrite", (store) => store.put(entry));
  return entry;
}

export async function listQueued(): Promise<QueuedInspection[]> {
  const entries = await tx<QueuedInspection[]>("readonly", (store) => store.getAll());
  return entries.sort((a, b) => a.queuedAt - b.queuedAt);
}

export async function remove(id: string): Promise<void> {
  await tx("readwrite", (store) => store.delete(id));
}

export interface FlushResult {
  sent: number;
  failed: number;
  scanIds: string[];
}

/** Send queued inspections one at a time. Stops at the first network failure so the
 *  queue order is preserved and nothing is sent twice. */
export async function flush(): Promise<FlushResult> {
  const queued = await listQueued();
  const result: FlushResult = { sent: 0, failed: 0, scanIds: [] };

  for (const entry of queued) {
    try {
      const response = await api.createScan({
        ...entry.input,
        image: new File([entry.image], entry.imageName, { type: entry.image.type }),
      });
      await remove(entry.id);
      result.sent += 1;
      result.scanIds.push(response.scan.id);
    } catch (error) {
      // A rejection from the server (bad frame, provider failure) is a real answer, not a
      // connectivity problem: drop it from the queue so it is not retried forever.
      if (error instanceof Error && "status" in error && typeof error.status === "number") {
        await remove(entry.id);
        result.failed += 1;
        continue;
      }
      break;
    }
  }

  return result;
}

/** Shared queue status, so the sidebar's sync indicator and the capture page's own
 *  banner read the same number rather than each polling IndexedDB independently. */
export function useQueueStatus() {
  const [count, setCount] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [lastResult, setLastResult] = useState<FlushResult | null>(null);
  const [online, setOnline] = useState(() => navigator.onLine);

  const refresh = useCallback(async () => {
    setCount((await listQueued()).length);
  }, []);

  const sync = useCallback(async () => {
    setSyncing(true);
    try {
      const result = await flush();
      if (result.sent || result.failed) setLastResult(result);
      return result;
    } finally {
      setSyncing(false);
      await refresh();
    }
  }, [refresh]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const goOnline = () => {
      setOnline(true);
      sync();
    };
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, [sync]);

  return { count, syncing, online, lastResult, refresh, sync, clearResult: () => setLastResult(null) };
}
