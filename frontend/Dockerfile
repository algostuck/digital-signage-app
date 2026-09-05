# Portal image: build the static bundle, serve it with nginx.
#
# nginx does three things a static host must do for this app: serve the
# SPA with history-mode fallback, proxy /api to the API service (same
# origin, so no CORS and no token in a cross-site request), and send the
# security headers (Content-Security-Policy in particular) that the API
# cannot set for HTML it does not serve.

FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/healthz >/dev/null || exit 1
EXPOSE 80
