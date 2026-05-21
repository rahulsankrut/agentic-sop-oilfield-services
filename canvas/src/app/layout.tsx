import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { RehearsalControls } from "@/components/demo/RehearsalControls";
import { getActiveSkin } from "@/lib/skin";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Skin is build-time-bundled; reading it at module load is safe and lets us
// produce dynamic <Metadata> + brand CSS vars without a client roundtrip.
const SKIN = getActiveSkin();

export const metadata: Metadata = {
  title: `Operations Canvas — ${SKIN.meta.customer_display_name}`,
  description:
    SKIN.meta.tagline ?? "Companion view for the Capacity Orchestrator Agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Brand CSS variables — consumed by skin-aware components (Tailwind utility
  // `[color:var(--color-brand-primary)]` etc.). Defined here at the root so
  // every page picks them up automatically.
  const brandStyle = {
    ["--color-brand-primary" as string]: SKIN.meta.color_primary,
    ["--color-brand-secondary" as string]: SKIN.meta.color_secondary,
    ["--color-brand-accent" as string]: SKIN.meta.color_accent,
  } as React.CSSProperties;

  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}
      style={brandStyle}
      data-skin={SKIN.meta.customer_slug}
    >
      <body className="h-screen overflow-hidden">
        {children}
        <RehearsalControls />
      </body>
    </html>
  );
}
