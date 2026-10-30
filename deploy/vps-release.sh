#!/bin/sh
# Run from an immutable release directory containing its private .env.vps link.
set -eu
cd "${1:?Usage: sh deploy/vps-release.sh /opt/nota-tecnica/releases/COMMIT}"

compose() {
    docker compose --env-file .env.vps -f docker-compose.vps.yml "$@"
}

compose config -q
compose build api
# Preserve existing database/Redis containers and volumes on later releases.
compose up -d --no-recreate postgres redis
# Fail before replacing any application container. Schema migrations must
# remain compatible with the application version still serving requests.
compose run --rm --no-deps migrate
# Migration already succeeded: do not start/recreate its service again here.
compose up -d --no-deps --wait --wait-timeout 120 api worker beat
