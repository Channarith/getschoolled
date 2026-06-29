# syntax=docker/dockerfile:1
FROM node:22-slim AS deps
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm install

FROM node:22-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web ./
# Stamp the real build version into the client bundle so the deployed UI always
# shows the version of THIS build, not a stale committed GENERATED_VERSION.
# Precedence: --build-arg APP_VERSION  >  repo VERSION file  >  GENERATED_VERSION.
# The repo VERSION file is copied from the build context (context is the repo
# root in CI); if it is absent the build falls back to GENERATED_VERSION.
COPY VERSIO[N] ./_repo_version
ARG APP_VERSION=""
RUN APP_VERSION="${APP_VERSION:-$(cat ./_repo_version 2>/dev/null || true)}"; \
    rm -f ./_repo_version; \
    echo "Building web with NEXT_PUBLIC_APP_VERSION='${APP_VERSION}'"; \
    NEXT_PUBLIC_APP_VERSION="${APP_VERSION}" npm run build

FROM node:22-slim AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["npm", "start"]
