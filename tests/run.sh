#!/bin/bash
# usage: tests/run.sh <script.txt> [debug]   - runs a harness script against build/ (or build-debug/)
T=/home/lolz0r/earthbound
B=build; [ "$2" = "debug" ] && B=build-debug
cd "$T/tests" && mkdir -p out && EBH_MAP="$T/ebsrc/$B/earthbound.map" "$T/tools/bin/ebharness" "$T/tools/snes9x/libretro/snes9x_libretro.so" "$T/ebsrc/$B/earthbound.sfc" "$1" out 2>&1 | grep -v "^loaded\|^Map_\|^shot\|^poke"
