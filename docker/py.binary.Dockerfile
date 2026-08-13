FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ngrep ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG user=1000
ARG group=1000

USER $user:$group
WORKDIR /app

COPY --chown=$user:$group --chmod=755 main .

ENTRYPOINT ["/app/main"]