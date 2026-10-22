#!/bin/sh
set -eu
project=$1
qa=${2:-/mnt/d/B2B_8case-runtime/video-qa}
mkdir -p "$qa"
movie="$project/docs/media/deykstra-demo.mp4"
ffprobe -v error -show_format -show_streams -of json "$movie" > "$project/docs/video-report.json"
for second in 5 85 135 200 250; do
  ffmpeg -loglevel error -y -ss "$second" -i "$movie" -frames:v 1 "$qa/$second.png"
done
