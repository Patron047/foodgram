# Этап 1: Сборка фронтенда
FROM node:21.7.1-alpine AS build

WORKDIR /app

COPY package*.json ./

RUN npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retry-maxtimeout 120000 && \
    npm config set fetch-retries 5 && \
    npm install --legacy-peer-deps

COPY . ./

RUN npm run build

# Этап 2: Финальный образ с Nginx
FROM nginx:stable-alpine

# Копируем собранную сборку ИЗ СТАНДАРТНОЙ ПАПКИ build
COPY --from=build /app/build/ /usr/share/nginx/html/

# Запускаем nginx
CMD ["nginx", "-g", "daemon off;"]