FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
LABEL org.opencontainers.image.source="https://github.com/p4xx07/ripiano"
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY real-ip.sh /docker-entrypoint.d/30-ripiano-real-ip.sh
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
