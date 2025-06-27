FROM golang:1.23.4-alpine AS builder
RUN apk add --no-cache git build-base

WORKDIR /src
RUN git clone https://github.com/sourcegraph/zoekt.git .

RUN go build -o /usr/local/bin/zoekt-git-index ./cmd/zoekt-git-index
RUN go build -o /usr/local/bin/zoekt-index     ./cmd/zoekt-index
RUN go build -o /usr/local/bin/zoekt-webserver ./cmd/zoekt-webserver

# Stage runtime
FROM alpine:3.18
RUN apk add --no-cache bash

# Copy Zoekt binaries
COPY --from=builder /usr/local/bin/zoekt* /usr/local/bin/

RUN mkdir -p /data/repos /data/index

WORKDIR /data

ENTRYPOINT [ "sh", "-c", "\
    echo '🔍 Indexing all repositories...'; \
    zoekt-index -index /data/index /data/repos; \
    echo '🚀 Starting Zoekt webserver on :6070'; \
    exec zoekt-webserver -index /data/index -listen :6070 -rpc" ]
