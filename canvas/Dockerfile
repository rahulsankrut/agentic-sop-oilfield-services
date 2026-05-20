# Multi-stage build for the Operations Canvas (Next.js 16 standalone).
# Image size target: ~150 MB. Build target: Cloud Run.

# ---- Stage 1: install deps ----
FROM node:20-alpine AS deps
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

# ---- Stage 2: build ----
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time Google Maps Platform API key (baked into client JS). Override
# via Cloud Build substitution or `docker build --build-arg`. The demo
# deploy MUST use an HTTP-referrer-restricted key; see
# canvas/src/components/canvas/GlobalMap.tsx for the runtime constraint.
# Optional NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID selects a cloud-managed map
# style (preferred over the inline dark style in production).
ARG NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
ENV NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=$NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
ARG NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID
ENV NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID=$NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- Stage 3: runtime ----
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=8080
ENV HOSTNAME=0.0.0.0

# Cloud Run unprivileged user.
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Standalone output bundles only what's needed at runtime.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 8080

CMD ["node", "server.js"]
