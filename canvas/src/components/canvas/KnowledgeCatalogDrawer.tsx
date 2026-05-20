"use client";

import { motion } from "framer-motion";
import { ArrowRight, Database } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CrossSystemAliases {
  sap_material_number?: string;
  maximo_equipment_id?: string;
  fdp_config_id?: string;
  intouch_spec_refs?: string[];
}

interface FunctionalEquivalent {
  equivalent_canonical_id?: string;
  canonical_id?: string;
  confidence?: number;
  rationale_source?: string;
}

interface FunctionalEquivalence {
  equivalents?: FunctionalEquivalent[];
}

interface KnowledgeCatalogDrawerProps {
  canonicalId: string;
  canonicalLabel: string;
  /**
   * Loose JSON payload from the Knowledge Catalog. We do not assume any
   * particular shape — every section gracefully degrades to an empty state.
   */
  aspects: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Helpers — narrow the loose `aspects` payload safely
// ---------------------------------------------------------------------------

function readRecord(value: unknown): Record<string, unknown> | undefined {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return undefined;
}

function readString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function readNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function formatSpecKey(key: string): string {
  return key
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatSpecValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

// DEMO NARRATION (Beat 5/8 of cargo-plane storyboard):
// "Here's why the agent never got confused. Knowledge Catalog's managed
// remote MCP server returned this canonical entity. SAP calls it MAT-67890,
// Maximo calls it EQ-12345, FDP has its own ID. The agent never sees that
// chaos. One canonical entity, all aliases, equivalence relationships
// with spec citations. This is your Issue 4 — dissolved."
export function KnowledgeCatalogDrawer({
  canonicalId,
  canonicalLabel,
  aspects,
}: KnowledgeCatalogDrawerProps) {
  const specification = readRecord(aspects.asset_specification);
  const aliases = readRecord(aspects.cross_system_aliases) as
    | CrossSystemAliases
    | undefined;
  const equivalence = readRecord(aspects.functional_equivalence) as
    | FunctionalEquivalence
    | undefined;

  const intouchRefs = readStringArray(aliases?.intouch_spec_refs);
  const equivalents: FunctionalEquivalent[] = Array.isArray(
    equivalence?.equivalents,
  )
    ? (equivalence?.equivalents as FunctionalEquivalent[])
    : [];

  return (
    <motion.div
      initial={{ x: 32, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 32, opacity: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="flex h-full flex-col gap-5 p-6"
    >
      {/* Header */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <Database
            className="h-4 w-4"
            style={{ color: "var(--color-knowledge-catalog)" }}
          />
          <span
            className="text-[10px] font-medium uppercase tracking-[0.18em]"
            style={{ color: "var(--color-knowledge-catalog)" }}
          >
            Knowledge Catalog
          </span>
        </div>
        <h2 className="mb-2 text-2xl leading-tight font-semibold text-white">
          {canonicalLabel}
        </h2>
        <Badge
          variant="outline"
          className="border-white/20 font-mono text-[11px] text-white/70"
        >
          {canonicalId}
        </Badge>
      </div>

      {/* Tabbed sections */}
      <Tabs defaultValue="specification" className="flex-1">
        <TabsList variant="line" className="w-full justify-start">
          <TabsTrigger value="specification">Specification</TabsTrigger>
          <TabsTrigger value="aliases">Aliases</TabsTrigger>
          <TabsTrigger value="equivalence">Equivalence</TabsTrigger>
        </TabsList>

        {/* Specification --------------------------------------------------- */}
        <TabsContent value="specification" className="mt-4">
          {specification && Object.keys(specification).length > 0 ? (
            <Card className="border-0 bg-white/[0.04] ring-1 ring-white/10">
              <CardContent className="p-4">
                <dl className="space-y-2.5">
                  {Object.entries(specification).map(([key, value]) => (
                    <div
                      key={key}
                      className="flex items-start justify-between gap-4 border-b border-white/5 pb-2.5 last:border-0 last:pb-0"
                    >
                      <dt className="text-xs text-white/55">
                        {formatSpecKey(key)}
                      </dt>
                      <dd className="text-right font-mono text-xs text-white/90">
                        {formatSpecValue(value)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </CardContent>
            </Card>
          ) : (
            <EmptyState message="No specification recorded" />
          )}
        </TabsContent>

        {/* Aliases --------------------------------------------------------- */}
        <TabsContent value="aliases" className="mt-4">
          {aliases &&
          (readString(aliases.sap_material_number) ||
            readString(aliases.maximo_equipment_id) ||
            readString(aliases.fdp_config_id) ||
            intouchRefs.length > 0) ? (
            <Card className="border-0 bg-white/[0.04] ring-1 ring-white/10">
              <CardContent className="space-y-3 p-4">
                <AliasRow label="SAP material #" value={aliases.sap_material_number} />
                <AliasRow label="Maximo equipment" value={aliases.maximo_equipment_id} />
                <AliasRow label="FDP config" value={aliases.fdp_config_id} />
                {intouchRefs.length > 0 && (
                  <div className="border-t border-white/5 pt-3">
                    <div className="mb-2 text-xs text-white/55">InTouch specs</div>
                    <div className="flex flex-wrap gap-1.5">
                      {intouchRefs.map((ref) => (
                        <Badge
                          key={ref}
                          variant="outline"
                          className="border-white/15 font-mono text-[10px] text-white/80"
                        >
                          {ref}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <EmptyState message="No aliases recorded" />
          )}
        </TabsContent>

        {/* Equivalence ----------------------------------------------------- */}
        <TabsContent value="equivalence" className="mt-4">
          {equivalents.length > 0 ? (
            <div className="space-y-3">
              {equivalents.map((eq, idx) => {
                const id =
                  readString(eq.equivalent_canonical_id) ??
                  readString(eq.canonical_id) ??
                  `equivalent-${idx}`;
                const confidence = readNumber(eq.confidence);
                const source = readString(eq.rationale_source);

                return (
                  <Card
                    key={`${id}-${idx}`}
                    className="border-0 bg-white/[0.04] ring-1 ring-white/10"
                  >
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="font-mono text-sm text-white">
                          {id}
                        </CardTitle>
                        {confidence !== undefined && (
                          <Badge
                            className="text-[10px]"
                            style={{
                              backgroundColor:
                                "color-mix(in srgb, var(--color-knowledge-catalog) 18%, transparent)",
                              color: "var(--color-knowledge-catalog)",
                            }}
                          >
                            {(confidence * 100).toFixed(0)}% confidence
                          </Badge>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent className="pt-0">
                      {source ? (
                        <div className="flex items-center gap-1.5 text-xs text-white/55">
                          <ArrowRight className="h-3 w-3" />
                          <span>Source: {source}</span>
                        </div>
                      ) : (
                        <div className="text-xs text-white/40">
                          No rationale source recorded
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          ) : (
            <EmptyState message="No functional equivalents recorded" />
          )}
        </TabsContent>
      </Tabs>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function AliasRow({ label, value }: { label: string; value?: unknown }) {
  const v = readString(value);
  if (!v) return null;
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-xs text-white/55">{label}</span>
      <span className="font-mono text-xs text-white/90">{v}</span>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed border-white/10 p-6 text-center text-xs text-white/40">
      {message}
    </div>
  );
}
