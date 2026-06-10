FROM node:21.7.1-alpine AS build

WORKDIR /app

COPY package*.json ./

RUN npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retry-maxtimeout 120000 && \
    npm config set fetch-retries 5 && \
    npm install --legacy-peer-deps

COPY . ./

RUN npm run build

FROM nginx:stable-alpine

COPY --from=build /app/result_build/ /usr/share/nginx/html/

CMD ["nginx", "-g", "daemon off;"]