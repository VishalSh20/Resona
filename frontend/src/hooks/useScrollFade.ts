import { useEffect, useRef, useState } from "react";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/**
 * Returns 0 → 1 progress as the page scrolls over `distance` px.
 * Stays at 0 for reduced-motion users so content never fades away.
 */
export function useScrollFade(distance = 600) {
  const [progress, setProgress] = useState(0);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    if (window.matchMedia(REDUCED_MOTION_QUERY).matches) return;

    const update = () => {
      frame.current = null;
      setProgress(Math.min(1, Math.max(0, window.scrollY / distance)));
    };
    const onScroll = () => {
      if (frame.current !== null) return;
      frame.current = requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [distance]);

  return progress;
}
