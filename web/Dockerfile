# syntax=docker/dockerfile:1
FROM node:20-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# Static files behind nginx, which also proxies /api to the API (no CORS, SSE unbuffered).
# nginx.conf is a template: the image's entrypoint fills in ${UP_API_UPSTREAM} at start (compose: http://api:8000,
# Kubernetes: the release's API service), leaving nginx's own $variables untouched.
FROM nginxinc/nginx-unprivileged:1.27-alpine
ENV UP_API_UPSTREAM=http://api:8000
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 8080
