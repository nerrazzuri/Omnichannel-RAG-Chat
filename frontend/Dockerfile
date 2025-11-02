# Multi-stage build for Next.js frontend

# Stage 1: Build stage
ARG NODE_BUILD_IMAGE=node:20-alpine
FROM ${NODE_BUILD_IMAGE} AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies (deterministic)
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Production stage
ARG NODE_RUN_IMAGE=node:20-alpine
FROM ${NODE_RUN_IMAGE} AS runner

# Set working directory
WORKDIR /app

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy package files
COPY package*.json ./

# Install production dependencies only (deterministic)
RUN npm ci --omit=dev && npm cache clean --force

# Copy built application from builder stage
COPY --from=builder /app/.next ./.next
# public is optional; copy only if exists
COPY --from=builder /app/next.config.js ./

# Set proper ownership
RUN chown -R nextjs:nodejs /app

# Switch to non-root user
USER nextjs

# Set production env and tini for signal handling
ENV NODE_ENV=production
RUN apk add --no-cache tini
ENTRYPOINT ["/sbin/tini", "--"]

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000 || exit 1

# Start the application
CMD ["npm", "start"]
