FROM public.ecr.aws/docker/library/alpine
WORKDIR /app

RUN apk add --no-cache libc6-compat

COPY main /app/main

ENTRYPOINT ["/app/main"]