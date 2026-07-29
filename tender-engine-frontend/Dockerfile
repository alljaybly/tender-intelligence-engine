# ============================================================
# STAGE 1: Build
#   Installs all Node dependencies and builds the Vite+React
#   application into static assets in the dist/ folder.
#   This stage is discarded after the build completes.
# ============================================================
FROM node:20-alpine AS build

# Set working directory
WORKDIR /app

# Copy package files FIRST to maximise Docker layer caching.
# npm ci only re-runs when lockfile changes.
COPY package.json package-lock.json ./

# Install exact dependency versions from lockfile.
# --ignore-scripts skips lifecycle hooks for faster install.
RUN npm ci --ignore-scripts

# Copy the rest of the application source code.
COPY . .

# Build the production bundle (tsc + vite).
RUN npm run build

# ============================================================
# STAGE 2: Serve
#   Minimal nginx image serving the built static assets.
#   nginx is battle-tested for static file serving with
#   automatic compression, caching headers, and low overhead.
# ============================================================
FROM nginx:alpine

# Copy built assets from the build stage into nginx html dir.
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx config for SPA routing and API proxy.
# The config handles client-side routing fallback and proxies
# /api requests to the FastAPI backend.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Document the port nginx listens on.
EXPOSE 5173

# Health check verifies the server responds on the expected port.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:5173/ || exit 1

# Start nginx in foreground (daemon off for container).
CMD ["nginx", "-g", "daemon off;"]
