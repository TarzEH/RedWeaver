# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
# Backend URL when frontend is served (e.g. same host or backend service name)
ARG VITE_BACKEND_URL=/api
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
RUN npm run build

# Serve stage — same base image as build so the daemon only pulls node:20-alpine once.
# nginx is installed via Alpine apk (not the nginx:alpine image), which avoids a second
# Docker Hub pull that often fails behind flaky proxies (e.g. proxyconnect timeout).
FROM node:20-alpine AS runtime

RUN apk add --no-cache nginx

COPY --from=build /app/dist /usr/share/nginx/html
# Alpine’s nginx package uses http.d (not conf.d)
COPY nginx.conf /etc/nginx/http.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
