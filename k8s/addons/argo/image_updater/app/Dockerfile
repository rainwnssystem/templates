FROM public.ecr.aws/docker/library/golang:alpine
WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY main.go ./
RUN go build -o main .
RUN chmod +x ./main

CMD ["./main"]