FROM node:22-alpine AS frontend-build

WORKDIR /app

COPY web/package*.json ./
RUN npm ci

COPY web/ ./
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build


FROM python:3.11-slim AS app

WORKDIR /mbase

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN mkdir -p API
COPY API/requirements.txt ./API/requirements.txt
RUN pip install --no-cache-dir -r API/requirements.txt

COPY . .
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/start.sh /usr/local/bin/mangamanage-start
COPY --from=frontend-build /app/dist /usr/share/nginx/html
RUN mkdir -p \
        /tmp/nginx/client_body \
        /tmp/nginx/proxy \
        /tmp/nginx/fastcgi \
        /tmp/nginx/uwsgi \
        /tmp/nginx/scgi \
    && chmod -R 777 /tmp/nginx \
    && chmod +x /usr/local/bin/mangamanage-start

EXPOSE 8080

CMD ["mangamanage-start"]
