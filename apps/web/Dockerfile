# syntax=docker/dockerfile:1
# Build context MUST be the repo root (not apps/web): COPY paths below are
# apps/web/... — see .github/workflows/deploy.yml build-web job (context: .).
FROM node:22-slim AS deps
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm install

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
EXPOSE 3000
CMD ["npm", "start"]
