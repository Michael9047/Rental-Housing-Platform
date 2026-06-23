# ---- Build Stage ----
FROM node:22-alpine AS builder

WORKDIR /build

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

# ---- Nginx Runtime Stage ----
FROM nginx:1.27-alpine AS runtime

LABEL org.opencontainers.image.title="Rental Housing Frontend"
LABEL org.opencontainers.image.description="Vue 3 SPA frontend for rental housing matching system"

RUN rm -f /etc/nginx/conf.d/default.conf

COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
