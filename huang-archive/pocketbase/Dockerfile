FROM alpine:3.20

ARG PB_VERSION=0.22.26

RUN apk add --no-cache \
    ca-certificates \
    unzip \
    wget \
    curl \
    && update-ca-certificates

ADD https://github.com/pocketbase/pocketbase/releases/download/v${PB_VERSION}/pocketbase_${PB_VERSION}_linux_amd64.zip /tmp/pb.zip
RUN unzip /tmp/pb.zip -d /pb/ && rm /tmp/pb.zip && chmod +x /pb/pocketbase

COPY pb_migrations /pb/pb_migrations
COPY pb_hooks /pb/pb_hooks
COPY entrypoint.sh /pb/entrypoint.sh
RUN chmod +x /pb/entrypoint.sh

WORKDIR /pb
EXPOSE 8090
VOLUME ["/pb/pb_data"]

ENTRYPOINT ["/pb/entrypoint.sh"]
