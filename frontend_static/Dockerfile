FROM node:21.7.1-alpine AS build

WORKDIR /app

COPY package*.json ./

RUN npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retry-maxtimeout 120000 && \
    npm config set fetch-retries 5 && \
    npm install

COPY . ./

RUN npm run build

RUN mkdir -p /app/result_build

RUN cp -r build/* result_build/

CMD ["sh", "-c", "echo 'Frontend build completed. Files are in /app/result_build'"]