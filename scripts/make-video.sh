#!/bin/sh
set -eu
video=$1
project=$2
runtime=${3:-/mnt/d/B2B_8case-runtime/demo-recording}
ffmpeg -loglevel error -y -f concat -safe 0 -i "$runtime/audio-list.txt" -c:a pcm_s16le "$runtime/narration.wav"
ffmpeg -loglevel error -y -i "$video" -i "$runtime/narration.wav" -vf 'scale=1280:-2' \
  -c:v libx264 -preset fast -crf 24 -r 25 -c:a aac -b:a 128k -shortest -movflags +faststart \
  "$project/docs/media/deykstra-demo.mp4"
