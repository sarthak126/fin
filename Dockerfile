FROM node:20-alpine AS builder

WORKDIR /app
ARG INTERNAL_API_URL=http://127.0.0.1:8000/api/v1
ENV INTERNAL_API_URL=${INTERNAL_API_URL}
COPY package*.json ./
RUN npm ci
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ARG INTERNAL_API_URL=http://127.0.0.1:8000/api/v1
ENV INTERNAL_API_URL=${INTERNAL_API_URL}

COPY --from=builder /app/next.config.ts ./
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000
CMD ["npm", "start"]
