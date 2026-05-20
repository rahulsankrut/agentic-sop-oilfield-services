"use client";

import { ReactNode } from "react";

interface CanvasShellProps {
  chat: ReactNode;
  canvas: ReactNode;
  drawer?: ReactNode;
  drawerOpen?: boolean;
}

/**
 * Three-panel layout: embedded chat (left) | canvas (center) | drawer (right).
 *
 * The drawer column animates open/closed by transitioning the grid template.
 * The canvas always fills the center column so Mapbox can resize cleanly.
 */
export function CanvasShell({
  chat,
  canvas,
  drawer,
  drawerOpen = false,
}: CanvasShellProps) {
  return (
    <div
      className="grid h-screen"
      style={{
        gridTemplateColumns: `360px 1fr ${drawerOpen ? "420px" : "0px"}`,
        transition: "grid-template-columns 400ms cubic-bezier(0.4, 0, 0.2, 1)",
      }}
    >
      <aside
        className="overflow-y-auto border-r border-white/10"
        style={{ background: "var(--color-bg-elevated)" }}
      >
        {chat}
      </aside>

      <main className="relative overflow-hidden">{canvas}</main>

      <aside
        className={`overflow-y-auto border-l border-white/10 ${
          drawerOpen ? "" : "pointer-events-none"
        }`}
        style={{ background: "var(--color-bg-elevated)" }}
      >
        {drawerOpen && drawer}
      </aside>
    </div>
  );
}
