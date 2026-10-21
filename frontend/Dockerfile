# --- dependencies ---
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- build: rewrites to the backend are resolved here, so BACKEND_URL is a build arg ---
FROM node:24-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG BACKEND_URL=http://backend:8000
# Public settings are inlined into the browser bundle at build time (never put secrets here).
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ARG NEXT_PUBLIC_CONTACT_EMAIL=privacy@notemind.example
ARG NEXT_PUBLIC_TURNSTILE_SITE_KEY=
ARG FORCE_HTTPS=false
ENV BACKEND_URL=$BACKEND_URL NEXT_TELEMETRY_DISABLED=1     NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL NEXT_PUBLIC_CONTACT_EMAIL=$NEXT_PUBLIC_CONTACT_EMAIL     NEXT_PUBLIC_TURNSTILE_SITE_KEY=$NEXT_PUBLIC_TURNSTILE_SITE_KEY FORCE_HTTPS=$FORCE_HTTPS
RUN npm run build && npm run check:bundle

# --- runtime: standalone server only, non-root ---
FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
COPY --from=build --chown=app:app /app/client-ip.mjs ./client-ip.mjs
USER app
EXPOSE 3000
# client-ip.mjs: the backend must see the visitor's real address, never one they made up.
CMD ["node", "--import", "./client-ip.mjs", "server.js"]
