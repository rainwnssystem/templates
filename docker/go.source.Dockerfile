FROM alpine
WORKDIR /app

RUN apk add --no-cache libc-dev

COPY main /app/main

RUN /app/main