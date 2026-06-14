FROM node:20-alpine AS build

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci

# Pass environment variables to Vite build
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ARG VITE_MAPBOX_TOKEN
ENV VITE_MAPBOX_TOKEN=$VITE_MAPBOX_TOKEN
ARG VITE_DEMO_MODE
ENV VITE_DEMO_MODE=$VITE_DEMO_MODE
ARG VITE_MAX_AGENTS
ENV VITE_MAX_AGENTS=$VITE_MAX_AGENTS

COPY frontend ./
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
