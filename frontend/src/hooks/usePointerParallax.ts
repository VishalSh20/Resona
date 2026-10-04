import { useEffect, useRef, useState } from "react";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

interface PointerParallaxOptions {
  /** Max translation in px applied at the viewport edge. */
  range?: number;
}

/**
 * Tracks the pointer as a normalized offset, scaled to `range` px and rAF-throttled.
 * Returns `{ x: 0, y: 0 }` for reduced-motion users.
 */
export function usePointerParallax({ range = 6 }: PointerParallaxOptions = {}) {
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const frame = useRef<number | null>(null);
  const target = useRef({ x: 0, y: 0 });

  useEffect(() => {
    if (window.matchMedia(REDUCED_MOTION_QUERY).matches) return;

    const onPointerMove = (event: PointerEvent) => {
      target.current = {
        x: (event.clientX / window.innerWidth) * 2 - 1,
        y: (event.clientY / window.innerHeight) * 2 - 1,
      };
      if (frame.current !== null) return;
      frame.current = requestAnimationFrame(() => {
        frame.current = null;
        setOffset({
          x: target.current.x * range,
          y: target.current.y * range,
        });
      });
    };

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [range]);

  return offset;
}
