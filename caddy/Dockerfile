FROM caddy:2-alpine

COPY caddy/Caddyfile /etc/caddy/Caddyfile

# Every {$VAR} in the file carries a default, so this validates at build time
# with nothing set. A bare {$PORT} would adapt to the invalid address ":".
RUN caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

EXPOSE 8080

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
