import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/** `loop` is configuration, not a state — a looping playlist never reaches
 * `completed`, it just wraps. */
export type PlaybackStatus = "idle" | "playing" | "paused" | "completed";

export interface PlaybackSlot {
  /** Stable identity for this slot; timing resets when it changes. */
  key: string;
  /** Null means the duration is not known yet and must be reported by the
   * media element once its metadata loads. */
  durationMs: number | null;
}

export interface Playback {
  index: number;
  status: PlaybackStatus;
  elapsedMs: number;
  /** Resolved duration of the current slot, or null while still unknown. */
  currentDurationMs: number | null;
  loopCount: number;
  play(): void;
  pause(): void;
  toggle(): void;
  restart(): void;
  goTo(index: number): void;
  next(): void;
  previous(): void;
  /** Media elements call this when `durationMs` was null. */
  reportNaturalDuration(key: string, ms: number): void;
}

/**
 * Drives one timeline. The clock is a rAF loop accumulating real deltas, so
 * pausing genuinely stops time rather than merely hiding it, and a tab that
 * is throttled in the background does not fast-forward on return.
 */
export function usePlayback(slots: PlaybackSlot[], loop: boolean, autoPlay = true): Playback {
  const [index, setIndex] = useState(0);
  const [status, setStatus] = useState<PlaybackStatus>(autoPlay ? "playing" : "idle");
  const [elapsedMs, setElapsedMs] = useState(0);
  const [loopCount, setLoopCount] = useState(0);
  const [natural, setNatural] = useState<Record<string, number>>({});

  // Reset whenever the track itself changes (different playlist, reordered
  // items) rather than on every render of an equal-but-new array.
  const signature = useMemo(() => slots.map((s) => s.key).join("|"), [slots]);
  useEffect(() => {
    setIndex(0);
    setElapsedMs(0);
    setLoopCount(0);
    setStatus(autoPlay ? "playing" : "idle");
  }, [signature, autoPlay]);

  const current = slots[index];
  const currentDurationMs = current
    ? (current.durationMs ?? natural[current.key] ?? null)
    : null;

  const lastFrameRef = useRef<number | null>(null);
  useEffect(() => {
    if (status !== "playing") {
      lastFrameRef.current = null;
      return;
    }
    let frame = 0;
    let cancelled = false;
    function tick(now: number) {
      if (cancelled) return;
      const last = lastFrameRef.current;
      lastFrameRef.current = now;
      if (last !== null) setElapsedMs((ms) => ms + (now - last));
      frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      lastFrameRef.current = null;
    };
  }, [status]);

  const advance = useCallback(() => {
    if (index + 1 < slots.length) {
      setIndex(index + 1);
      setElapsedMs(0);
      return;
    }
    if (loop && slots.length > 0) {
      setIndex(0);
      setElapsedMs(0);
      setLoopCount((count) => count + 1);
      return;
    }
    setStatus("completed");
  }, [index, slots.length, loop]);

  useEffect(() => {
    if (status !== "playing" || currentDurationMs === null) return;
    if (elapsedMs < currentDurationMs) return;
    advance();
  }, [status, elapsedMs, currentDurationMs, advance]);

  const goTo = useCallback(
    (target: number) => {
      if (target < 0 || target >= slots.length) return;
      setIndex(target);
      setElapsedMs(0);
      setStatus((s) => (s === "completed" ? "playing" : s));
    },
    [slots.length],
  );

  return {
    index,
    status,
    elapsedMs,
    currentDurationMs,
    loopCount,
    play: useCallback(() => setStatus("playing"), []),
    pause: useCallback(() => setStatus("paused"), []),
    toggle: useCallback(
      () => setStatus((s) => (s === "playing" ? "paused" : "playing")),
      [],
    ),
    restart: useCallback(() => {
      setIndex(0);
      setElapsedMs(0);
      setLoopCount(0);
      setStatus("playing");
    }, []),
    goTo,
    next: useCallback(() => {
      // An explicit skip past the end wraps even when loop is off, because
      // the operator asked for it; only automatic advancement completes.
      goTo(index + 1 < slots.length ? index + 1 : 0);
    }, [goTo, index, slots.length]),
    previous: useCallback(() => {
      goTo(index > 0 ? index - 1 : Math.max(0, slots.length - 1));
    }, [goTo, index, slots.length]),
    reportNaturalDuration: useCallback((key: string, ms: number) => {
      setNatural((prev) => (prev[key] === ms ? prev : { ...prev, [key]: ms }));
    }, []),
  };
}

export function formatClock(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}
