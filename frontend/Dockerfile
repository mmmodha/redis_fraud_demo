FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_REDIS_CLOUD_URL
ARG NEXT_PUBLIC_CONTEXT_RETRIEVER_URL
ARG NEXT_PUBLIC_GITHUB_URL
ENV NEXT_PUBLIC_REDIS_CLOUD_URL=$NEXT_PUBLIC_REDIS_CLOUD_URL
ENV NEXT_PUBLIC_CONTEXT_RETRIEVER_URL=$NEXT_PUBLIC_CONTEXT_RETRIEVER_URL
ENV NEXT_PUBLIC_GITHUB_URL=$NEXT_PUBLIC_GITHUB_URL
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
RUN apk add --no-cache curl
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
