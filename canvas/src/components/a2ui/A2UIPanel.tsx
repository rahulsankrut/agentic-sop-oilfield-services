"use client";

/**
 * A2UIPanel — thin wrapper around @a2ui/react's <A2UIRenderer> for
 * agent-emitted UI surfaces. TASK-45.
 *
 * Each panel owns its own <A2UIProvider> + surface id, so multiple
 * panels can coexist on the same page without colliding on state.
 * The agent (or, for the demo, a static sample payload from
 * `canvas/src/data/a2uiSamples.ts`) supplies the messages.
 *
 * Surfaces stay non-spatial — the map remains bespoke (TASK-45 scope).
 */

import { useEffect } from "react";
import { A2UIProvider, A2UIRenderer, useA2UI } from "@a2ui/react";
import type { ServerToClientMessage } from "@a2ui/react";

interface MessagePumpProps {
  messages: ServerToClientMessage[];
}

function MessagePump({ messages }: MessagePumpProps) {
  const { processMessages, clearSurfaces } = useA2UI();
  useEffect(() => {
    clearSurfaces();
    processMessages(messages);
  }, [messages, processMessages, clearSurfaces]);
  return null;
}

interface A2UIPanelProps {
  /** The A2UI messages emitted for this panel — createSurface + updateComponents + beginRendering. */
  messages: ServerToClientMessage[];
  /** Surface id to render; must match the createSurface message in `messages`. */
  surfaceId: string;
  /** Optional wrapper className. */
  className?: string;
}

export function A2UIPanel({ messages, surfaceId, className }: A2UIPanelProps) {
  return (
    <A2UIProvider>
      <MessagePump messages={messages} />
      <div className={className}>
        <A2UIRenderer
          surfaceId={surfaceId}
          fallback={
            <div className="text-xs uppercase tracking-[0.18em] text-white/40">
              waiting for A2UI surface ({surfaceId})…
            </div>
          }
        />
      </div>
    </A2UIProvider>
  );
}
