# Multi-stage build for NestJS application

# Stage 1: Build stage
ARG NODE_BUILD_IMAGE=node:20-alpine
ARG NODE_RUN_IMAGE=node:20-alpine
FROM ${NODE_BUILD_IMAGE} AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all deps for build (deterministic)
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Copy source code
COPY src/ ./src/
COPY tsconfig*.json ./

# Build the application
RUN npm run build

# Stage 2: Production stage
FROM ${NODE_RUN_IMAGE} AS production

# Set working directory
WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 -S nodejs \
 && adduser -S nestjs -u 1001

# Copy package files
COPY package*.json ./

# Install production dependencies only (deterministic)
RUN if [ -f package-lock.json ]; then npm ci --omit=dev; else npm install --omit=dev; fi && npm cache clean --force

# Copy built application from builder stage
COPY --from=builder /app/dist ./dist

# Create logs directory
RUN mkdir -p logs && chown -R nestjs:nodejs /app

# Install tini as root (before switching user)
RUN apk add --no-cache tini wget

# Switch to non-root user
USER nestjs

# Set production env and use tini for signal handling
ENV NODE_ENV=production
ENTRYPOINT ["/sbin/tini", "--"]

# Expose port
EXPOSE 3001

HEALTHCHECK --interval=10s --timeout=2s --start-period=5s --retries=5 \
  CMD wget -q -T 2 -O - http://127.0.0.1:3001/healthz || exit 1

# Start the application
CMD ["npm", "run", "start:prod"]
