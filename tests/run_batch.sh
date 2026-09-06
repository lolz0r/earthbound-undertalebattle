#!/bin/bash
# usage: tests/run_batch.sh LOG test1 test2 ...  - runs each tests/<name>.txt, logging to LOG
LOG=$1; shift; : > "$LOG"
for t in "$@"; do
  echo "===== $t" >> "$LOG"
  timeout 900 /home/lolz0r/earthbound/tests/run.sh /home/lolz0r/earthbound/tests/$t.txt >> "$LOG" 2>&1
  echo "----- exit $?" >> "$LOG"
done
echo "BATCH DONE" >> "$LOG"
