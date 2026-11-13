FROM node:22-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
WORKDIR /sdk
COPY snippet/ ./
RUN npm ci && npm run typecheck && npm test -- --pool=forks --poolOptions.forks.singleFork && npm run build
WORKDIR /app
COPY api/ ./
RUN npm ci && npx prisma generate && npm run typecheck && npm test -- --maxWorkers=1 && npm run build && npm prune --omit=dev

FROM node:22-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/dist ./dist
COPY --from=build /app/prisma ./prisma
COPY --from=build /sdk/dist ./sdk
USER node
EXPOSE 8080
CMD ["node", "dist/main.js"]
