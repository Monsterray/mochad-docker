###############################################################################
# Build Stage
###############################################################################
FROM alpine:3.22 AS builder

LABEL stage="builder"

RUN apk add --no-cache \
    git \
    build-base \
    automake \
    autoconf \
    libtool \
    libusb-dev

WORKDIR /src

ARG MOCHAD_REPOSITORY=https://github.com/Monsterray/mochad-redux.git
ARG MOCHAD_REF
# Deprecated compatibility alias. Prefer MOCHAD_REF.
ARG MOCHAD_COMMIT
ARG MOCHAD_REDUX_REVISION

RUN set -eux; \
    git clone "${MOCHAD_REPOSITORY}" .; \
    checkout_ref="${MOCHAD_REF:-${MOCHAD_COMMIT:-develop}}"; \
    git checkout "${checkout_ref}"; \
    actual_revision="$(git rev-parse HEAD)"; \
    if [ -n "${MOCHAD_REDUX_REVISION:-}" ] && [ "${MOCHAD_REDUX_REVISION}" != "unknown" ] && [ "${MOCHAD_REDUX_REVISION}" != "${actual_revision}" ]; then \
        echo "MOCHAD_REDUX_REVISION=${MOCHAD_REDUX_REVISION} does not match checked out source ${actual_revision}" >&2; \
        exit 1; \
    fi; \
    printf '%s\n' "${actual_revision}" > /tmp/mochad-source-revision

RUN chmod +x autogen.sh

RUN ./autogen.sh

RUN make
RUN make DESTDIR=/tmp/install install

RUN set -eux; \
    mkdir -p /tmp/runtime-licenses/mochad-redux; \
    for file in COPYING NOTICE docs/source-lineage.md; do \
        if [ -f "$file" ]; then \
            mkdir -p "/tmp/runtime-licenses/mochad-redux/$(dirname "$file")"; \
            cp "$file" "/tmp/runtime-licenses/mochad-redux/$file"; \
        else \
            printf 'Source checkout did not provide %s. Use audited mochad-redux source for release images.\n' "$file" > "/tmp/runtime-licenses/mochad-redux/$(basename "$file").missing"; \
        fi; \
    done


###############################################################################
# Runtime Stage
###############################################################################
FROM alpine:3.22

ARG BUILD_DATE=1970-01-01T00:00:00Z
ARG VCS_REF=unknown
ARG IMAGE_VERSION=0.1.0
ARG ALPINE_IMAGE=docker.io/library/alpine:3.22
ARG ALPINE_DIGEST=unknown
ARG MOCHAD_REPOSITORY=https://github.com/Monsterray/mochad-redux.git
ARG MOCHAD_REF=develop
ARG MOCHAD_REDUX_REVISION=unknown
ARG MOCHAD_REDUX_VERSION=unknown

LABEL org.opencontainers.image.title="mochad-docker"
LABEL org.opencontainers.image.description="X10 CM15A CM19A USB automation daemon"
LABEL org.opencontainers.image.version="${IMAGE_VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${VCS_REF}"
LABEL org.opencontainers.image.vendor="MQTT Mochad Bridge contributors"
LABEL org.opencontainers.image.url="https://github.com/Monsterray/mochad-docker"
LABEL org.opencontainers.image.source="https://github.com/Monsterray/mochad-docker"
LABEL org.opencontainers.image.documentation="https://github.com/Monsterray/mochad-docker"
LABEL org.opencontainers.image.licenses="MIT AND GPL-3.0-or-later"
LABEL org.opencontainers.image.base.name="${ALPINE_IMAGE}"
LABEL org.opencontainers.image.base.digest="${ALPINE_DIGEST}"
LABEL io.github.monsterray.mochad-redux.repository="${MOCHAD_REPOSITORY}"
LABEL io.github.monsterray.mochad-redux.revision="${MOCHAD_REDUX_REVISION}"
LABEL io.github.monsterray.mochad-redux.version="${MOCHAD_REDUX_VERSION}"

RUN apk add --no-cache \
    libusb-dev \
    su-exec \
    tini \
    tzdata \
    netcat-openbsd

COPY --from=builder \
    /tmp/install/usr/local/bin/mochad \
    /usr/local/bin/mochad

# Docker doesn't like systemd files or udev rules
COPY --from=builder \
    /src/udev/91-usb-x10-controllers.rules \
    /usr/share/mochad/91-usb-x10-controllers.rules

RUN mkdir -p /usr/share/licenses/mochad-docker /usr/share/licenses/mochad-redux
COPY LICENSE.md /usr/share/licenses/mochad-docker/LICENSE.md
COPY --from=builder \
    /tmp/runtime-licenses/mochad-redux/ \
    /usr/share/licenses/mochad-redux/
#
# COPY --from=builder \
#     /src/systemd/mochad.service \
#     /usr/share/mochad/mochad.service

EXPOSE 1099/tcp 1100/tcp 1101/tcp

COPY mochad-entrypoint.sh /usr/local/bin/mochad-entrypoint.sh
RUN chmod +x /usr/local/bin/mochad-entrypoint.sh \
    && mkdir -p /config

ENV PUID=911
ENV PGID=911
ENV USB_GID=auto
ENV USB_DEBUG=false
ENV TZ=UTC
ENV UMASK=022
ENV MOCHAD_FOREGROUND=true
ENV MOCHAD_RAW_DATA=false
ENV MOCHAD_BIND=0.0.0.0
ENV MOCHAD_PORT=1099
ENV MOCHAD_XML_ENABLED=true
ENV MOCHAD_XML_PORT=1100
ENV MOCHAD_OPENREMOTE_ENABLED=true
ENV MOCHAD_OPENREMOTE_PORT=1101
ENV MOCHAD_SHOW_VERSION=false
ENV MOCHAD_SHOW_HELP=false
ENV MOCHAD_ARGS=""

VOLUME ["/config"]

HEALTHCHECK --interval=30s \
            --timeout=5s \
            --start-period=10s \
            --retries=3 \
CMD bind="${MOCHAD_BIND:-0.0.0.0}"; \
    case "$bind" in \
      0.0.0.0) health_host=127.0.0.1 ;; \
      ::) health_host=::1 ;; \
      *) health_host="$bind" ;; \
    esac; \
    nc -z "$health_host" "${MOCHAD_PORT:-1099}" || exit 1

ENTRYPOINT ["/sbin/tini","--"]

CMD ["/usr/local/bin/mochad-entrypoint.sh"]
