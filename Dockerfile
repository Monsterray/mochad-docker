###############################################################################
# Build Stage
###############################################################################
FROM alpine:3.22 AS builder

LABEL stage="builder"

ARG BUILD_DATE
ARG VCS_REF

LABEL org.opencontainers.image.created=$BUILD_DATE
LABEL org.opencontainers.image.revision=$VCS_REF

RUN apk add --no-cache \
    git \
    build-base \
    automake \
    autoconf \
    libtool \
    libusb-dev

WORKDIR /src

ARG MOCHAD_COMMIT=master

RUN git clone https://github.com/sigmdel/mochad.git . \
 && git checkout ${MOCHAD_COMMIT}

RUN chmod +x autogen.sh

RUN ./autogen.sh

RUN make
RUN make DESTDIR=/tmp/install install


###############################################################################
# Runtime Stage
###############################################################################
FROM alpine:3.22

ARG BUILD_DATE
ARG VCS_REF
ARG IMAGE_VERSION=0.1.0

LABEL org.opencontainers.image.title="mochad"
LABEL org.opencontainers.image.description="X10 CM15A CM19A USB automation daemon"
LABEL org.opencontainers.image.version="${IMAGE_VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${VCS_REF}"
LABEL org.opencontainers.image.vendor="MQTT Mochad Bridge contributors"
LABEL org.opencontainers.image.url="https://github.com/Monsterray/mochad-docker"
LABEL org.opencontainers.image.source="https://github.com/Monsterray/mochad-docker"
LABEL org.opencontainers.image.documentation="https://github.com/Monsterray/mochad-docker"
LABEL org.opencontainers.image.licenses="GPL-2.0"

RUN apk add --no-cache \
    libusb-dev \
    tini \
    netcat-openbsd

COPY --from=builder \
    /tmp/install/usr/local/bin/mochad \
    /usr/local/bin/mochad

# Docker doesn't like systemd files or udev rules
COPY --from=builder \
    /src/udev/91-usb-x10-controllers.rules \
    /usr/share/mochad/91-usb-x10-controllers.rules
#
# COPY --from=builder \
#     /src/systemd/mochad.service \
#     /usr/share/mochad/mochad.service

EXPOSE 1099/tcp

COPY mochad-entrypoint.sh /usr/local/bin/mochad-entrypoint.sh
RUN chmod +x /usr/local/bin/mochad-entrypoint.sh

ENV MOCHAD_FOREGROUND=true
ENV MOCHAD_RAW_DATA=false
ENV MOCHAD_SHOW_VERSION=false
ENV MOCHAD_SHOW_HELP=false
ENV MOCHAD_ARGS=""

HEALTHCHECK --interval=30s \
            --timeout=5s \
            --start-period=10s \
            --retries=3 \
CMD nc -z localhost 1099 || exit 1

ENTRYPOINT ["/sbin/tini","--"]

CMD ["/usr/local/bin/mochad-entrypoint.sh"]
