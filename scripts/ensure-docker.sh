#!/bin/sh
set -eu
if docker info >/dev/null 2>&1; then
    exit 0
fi
nohup dockerd >/var/log/docker.log 2>&1 </dev/null &
for attempt in $(seq 1 30); do
    if docker info >/dev/null 2>&1; then
        exit 0
    fi
    sleep 1
done
exit 1
