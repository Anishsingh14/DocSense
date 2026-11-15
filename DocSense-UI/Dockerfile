# DocSense web UI. Built from the PROJECT ROOT (see docker-compose.yml) so the root .dockerignore applies.
# Stage 1: build the React app. Stage 2: serve it with nginx, which also proxies /api to the backend.
FROM node:20.18.0-alpine3.20 AS build
WORKDIR /ui
COPY DocSense-UI/package.json DocSense-UI/package-lock.json ./
RUN npm ci
COPY DocSense-UI/ ./
# The UI calls /api by default (src/lib/api.js), which nginx forwards to the backend.
RUN npm run build

FROM nginx:1.27.2-alpine
COPY DocSense-UI/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /ui/dist /usr/share/nginx/html
EXPOSE 80
