import { useEffect, useRef, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

/**
 * Applies a fade+slide-up entry animation only on the first mount.
 * Because React keys are stable (UUIDs), the component instance persists
 * across re-renders of the same message, so the animation never repeats.
 */
export function AnimatedMessageWrapper({ children }: Props) {
  const isFirstRender = useRef(true);
  const cls = isFirstRender.current
    ? "animate-in fade-in slide-in-from-bottom-2 duration-300"
    : "";

  useEffect(() => {
    isFirstRender.current = false;
  }, []);

  return <div className={cls}>{children}</div>;
}
