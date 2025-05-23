#!/bin/bash

USR="moflici1"
PRC="python"

while true; do
  ps aux | grep "$USR" | grep "$PRC" | grep -v grep | awk '{ sum+=$6 } END { print int(sum / 1024) }'
  sleep 0.1
done
