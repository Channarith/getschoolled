# syntax=docker/dockerfile:1
FROM node:22-slim AS deps
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
# npm ci installs exactly what the lockfile specifies, including platform-specific
# optional binaries (e.g. @next/swc-linux-x64-gnu) for the BUILD target OS/CPU.
# npm install resolves against the host OS that generated the lockfile (macOS) and
# skips Linux-only optionals, causing "Failed to load SWC binary" on every fresh build.
RUN npm ci

FROM node:22-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web ./
RUN npm run build

FROM node:22-slim AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/public ./public
# Legal pages (privacy/terms/data-deletion) read plain-text docs at runtime.
COPY --from=build /app/content ./content
EXPOSE 3000
CMD ["npm", "start"]
