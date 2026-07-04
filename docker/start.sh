#!/bin/sh
set -eu

mkdir -p \
    /tmp/nginx/client_body \
    /tmp/nginx/proxy \
    /tmp/nginx/fastcgi \
    /tmp/nginx/uwsgi \
    /tmp/nginx/scgi

python -m uvicorn API.fastapi:app --host 127.0.0.1 --port 8000 &
api_pid="$!"

nginx -g 'daemon off;' &
nginx_pid="$!"

term() {
    kill "$api_pid" 2>/dev/null || true
    kill "$nginx_pid" 2>/dev/null || true
    wait "$api_pid" 2>/dev/null || true
    wait "$nginx_pid" 2>/dev/null || true
}

trap term INT TERM

while kill -0 "$api_pid" 2>/dev/null && kill -0 "$nginx_pid" 2>/dev/null; do
    sleep 1
done

status=0
if ! kill -0 "$api_pid" 2>/dev/null; then
    wait "$api_pid" || status="$?"
fi
if ! kill -0 "$nginx_pid" 2>/dev/null; then
    wait "$nginx_pid" || status="$?"
fi

term
exit "$status"
