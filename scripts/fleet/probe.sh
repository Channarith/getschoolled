#!/usr/bin/env bash
# Read-only machine probe. Prints a compact report that aoep_shared.fleet_status parses.
# Runs locally or over `ssh host 'bash -s' < probe.sh`. Works on Linux and macOS.
# It never changes anything on the machine.
LC_ALL=C
export LC_ALL
HOME_DIR="${HOME:-$(cd ~ && pwd)}"
os="$(uname -s)"
echo "FLEET_PROBE 1"
echo "host=$(hostname -s 2>/dev/null || hostname)"
echo "os=$os"
echo "arch=$(uname -m)"
echo "now=$(date +%s)"

if [ "$os" = "Darwin" ]; then
  cpus="$(sysctl -n hw.ncpu 2>/dev/null)"
  memtotal_b="$(sysctl -n hw.memsize 2>/dev/null)"
  pagesz="$(vm_stat 2>/dev/null | awk '/page size of/ {print $8}')"
  case "$pagesz" in ''|*[!0-9]*) pagesz=4096 ;; esac
  freepages="$(vm_stat 2>/dev/null | awk '/Pages (free|inactive|speculative)/ {gsub(/\./,"",$NF); s+=$NF} END{print s+0}')"
  echo "load=$(sysctl -n vm.loadavg 2>/dev/null | tr -d '{}' | awk '{print $1, $2, $3}')"
  echo "mem_total_kb=$(( ${memtotal_b:-0} / 1024 ))"
  echo "mem_avail_kb=$(( ${freepages:-0} * pagesz / 1024 ))"
  echo "swap_used_kb=$(sysctl -n vm.swapusage 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="used") {v=$(i+2); u=substr(v,length(v)); n=v+0; if(u=="M") n*=1024; else if(u=="G") n*=1048576; printf "%d", n}}')"
else
  cpus="$(nproc 2>/dev/null || getconf _NPROCESSORS_ONLN)"
  echo "load=$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null)"
  awk '/^MemTotal:/ {print "mem_total_kb=" $2} /^MemAvailable:/ {print "mem_avail_kb=" $2} /^SwapTotal:/ {st=$2} /^SwapFree:/ {sf=$2} END {print "swap_used_kb=" st-sf}' /proc/meminfo 2>/dev/null
fi
echo "cpus=${cpus:-0}"
df -Pk / 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print "disk=/ " $2 " " $3 " " $4 " " $5}'

if command -v nvidia-smi >/dev/null 2>&1; then
  gpu_lines="$(nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits 2>/dev/null)"
  if [ -n "$gpu_lines" ]; then
    printf '%s\n' "$gpu_lines" | awk -F', *' '{printf "gpu=%s|%s|%s|%s|%s\n", $1, $2, $3, $4, $5}'
  else
    echo "gpu=none"
  fi
  nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2>/dev/null | awk -F', *' '$1 ~ /^[0-9]+$/ {print "gpu_app=" $1 "|" $2}'
else
  echo "gpu=none"
fi

PSFMT="user=,pid=,ppid=,stat=,etime=,pcpu=,rss=,args="
ps_all() { ps -axo "$PSFMT" 2>/dev/null | cut -c1-260; }
echo "[procs_cpu]"
ps_all | sort -k6 -nr | head -8
echo "[procs_rss]"
ps_all | sort -k7 -nr | head -8
echo "[zombies]"
ps_all | awk '$4 ~ /^Z/' | head -20
echo "[zombie_parents]"
for p in $(ps_all | awk '$4 ~ /^Z/ {print $3}' | sort -u | head -10); do
  ps -o "$PSFMT" -p "$p" 2>/dev/null | cut -c1-260
done
echo "[orphans]"
ps_all | awk '$3 == 1 && $1 != "root" && $8 ~ /python|uvicorn|node|llama|ffmpeg|yt-dlp|whisper|torch|nllb|translate/' | head -20
echo "[lock]"
lock="$HOME_DIR/.gs-gpu.lock"
echo "path=$lock"
if [ -e "$lock" ]; then
  holders=""
  if command -v fuser >/dev/null 2>&1; then
    holders="$(fuser "$lock" 2>/dev/null | tr -s ' ' | sed 's/^ //')"
  elif command -v lsof >/dev/null 2>&1; then
    holders="$(lsof -t "$lock" 2>/dev/null | sort -u | tr '\n' ' ')"
  fi
  echo "exists=yes"
  echo "holders=$holders"
else
  echo "exists=no"
fi
if [ -f "$lock.owner" ]; then
  echo "owner=$(head -1 "$lock.owner" | cut -c1-240)"
  opid="$(head -1 "$lock.owner" | awk '{print $1}')"
  if kill -0 "$opid" 2>/dev/null; then echo "owner_alive=yes"; else echo "owner_alive=no"; fi
fi
echo "[jobs]"
for f in "$HOME_DIR"/.gs-jobs/*.json; do
  [ -f "$f" ] || continue
  rec="$(tr -d '\n' < "$f" | cut -c1-600)"
  pid="$(sed -n 's/.*"pid": *\([0-9]*\).*/\1/p' "$f" | head -1)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then alive="alive"; else alive="dead"; fi
  echo "$rec #$alive"
done 2>/dev/null | tail -40
echo "[cosyvoice]"
for f in "$HOME_DIR/code/getschoolled/output/cosyvoice_voice_queue_status.json" "$HOME_DIR/getschoolled/output/cosyvoice_voice_queue_status.json"; do
  if [ -f "$f" ]; then
    tr -d '\n' < "$f" | cut -c1-3000
    echo
    echo "mtime=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null)"
    break
  fi
done
echo "[batch_logs]"
for f in "$HOME_DIR"/batch*.log "$HOME_DIR"/code/getschoolled/output/*batch*.log; do
  [ -f "$f" ] || continue
  mt="$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null)"
  printf '%s|%s|%s\n' "$(basename "$f")" "$mt" "$(tail -1 "$f" | cut -c1-160)"
done | head -10
echo "[timers]"
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user list-timers --all --no-pager 2>/dev/null | grep -iE "aoep|gs-|train|salareen" | cut -c1-200 | head -6
fi
# ---- who owns the busy processes -----------------------------------------------------------
# Candidates: top CPU, top memory, unmanaged orphans and parents of zombies. Read-only.
# Environment values are limited to a short allow-list; the whole environment is never printed.
cand="$( {
  ps_all | sort -k6 -nr | head -8 | awk '{print $2}'
  ps_all | sort -k7 -nr | head -8 | awk '{print $2}'
  ps_all | awk '$3 == 1 && $1 != "root" && $8 ~ /python|uvicorn|node|llama|ffmpeg|yt-dlp|whisper|torch|nllb|translate/ {print $2}' | head -6
  ps_all | awk '$4 ~ /^Z/ {print $3}' | head -6
} | awk 'NF && !seen[$1]++' | head -20)"

echo "[owners]"
for p in $cand; do
  echo "pid=$p"
  cwd=""
  if [ -d "/proc/$p" ]; then
    cwd="$(readlink "/proc/$p/cwd" 2>/dev/null)"
  elif command -v lsof >/dev/null 2>&1; then
    cwd="$(lsof -a -p "$p" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1)"
  fi
  echo "cwd=$cwd"
  if [ -n "$cwd" ] && [ -d "$cwd" ] && command -v git >/dev/null 2>&1; then
    top="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)"
    if [ -n "$top" ]; then
      gdir="$(git -C "$cwd" rev-parse --git-dir 2>/dev/null)"
      branch="$(git -C "$cwd" symbolic-ref --short -q HEAD 2>/dev/null || echo detached)"
      last="$(git -C "$cwd" log -1 --format='%h|%s' 2>/dev/null | cut -c1-90)"
      wt=0
      case "$gdir" in */worktrees/*) wt=1 ;; esac
      echo "git=$top|$wt|$branch|$last"
    fi
  fi
  if [ -r "/proc/$p/cgroup" ]; then echo "cgroup=$(head -1 "/proc/$p/cgroup" | cut -c1-200)"; fi
  chain=""; q="$p"; n=0
  while [ -n "$q" ] && [ "$q" -gt 1 ] 2>/dev/null && [ "$n" -lt 12 ]; do
    c="$(ps -o comm= -p "$q" 2>/dev/null | head -1)"
    c="${c##*/}"; c="$(printf '%s' "${c:-?}" | tr ' ' '_' | cut -c1-30)"
    chain="$chain $q:$c"
    q="$(ps -o ppid= -p "$q" 2>/dev/null | tr -d ' ')"
    n=$((n + 1))
  done
  echo "chain=${chain# }"
  if [ -r "/proc/$p/environ" ]; then
    envs="$(tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | grep -E '^(NLLB_DEVICE|CUDA_VISIBLE_DEVICES|NVIDIA_VISIBLE_DEVICES)=' | tr '\n' ' ')"
    echo "env=readable|$envs"
  else
    echo "env=unreadable|"
  fi
  best_t=""; best_m=0
  for fd in 1 2; do
    t="$(readlink "/proc/$p/fd/$fd" 2>/dev/null)"
    case "$t" in ""|/dev/*|socket:*|pipe:*|anon_inode:*) continue ;; esac
    [ -f "$t" ] || continue
    m="$(stat -c %Y "$t" 2>/dev/null)"
    [ -n "$m" ] || continue
    if [ "$m" -gt "$best_m" ]; then best_m="$m"; best_t="$t"; fi
  done
  if [ -n "$best_t" ]; then echo "log=$best_t|$best_m"; fi
done

echo "[tmux]"
if command -v tmux >/dev/null 2>&1; then
  {
    tmux list-panes -a -F '#{pane_pid} #{session_name} #{window_name}' 2>/dev/null
    for sock in /tmp/tmux-"$(id -u)"/*; do
      [ -S "$sock" ] || continue
      tmux -S "$sock" list-panes -a -F '#{pane_pid} #{session_name} #{window_name}' 2>/dev/null
    done
  } | sort -u | head -60
fi

echo "[sockets]"
if command -v ss >/dev/null 2>&1; then
  ss -H -tanp 2>/dev/null | awk '$1 == "LISTEN" || $1 == "ESTAB"' | head -400
fi

# ---- short CPU / IO sample: working or spinning? --------------------------------------------
# ps %CPU is an average over the whole life of the process, so a process that spun for an hour and
# then went quiet still looks busy. Two readings a few seconds apart show what it is doing now.
SAMPLE_SECONDS="${FLEET_SAMPLE_SECONDS:-10}"
case "$SAMPLE_SECONDS" in ''|*[!0-9]*) SAMPLE_SECONDS=10 ;; esac
echo "[sample]"
spin_cand="$(ps_all | awk '$6 + 0 >= 100 {print $2}' | head -6)"
if [ "$SAMPLE_SECONDS" -gt 0 ] && [ -n "$spin_cand" ]; then
  echo "interval=$SAMPLE_SECONDS"
  echo "clk_tck=$(getconf CLK_TCK 2>/dev/null || echo 100)"
  for p in $spin_cand; do
    tk="na"; io="na"
    if [ -r "/proc/$p/stat" ]; then tk="$(sed 's/.*) //' "/proc/$p/stat" 2>/dev/null | awk '{print $12 + $13}')"; fi
    if [ -r "/proc/$p/io" ]; then io="$(awk '/^rchar:|^wchar:/ {s += $2} END {print s + 0}' "/proc/$p/io" 2>/dev/null)"; fi
    echo "t0 $p ${tk:-na} ${io:-na}"
  done
  sleep "$SAMPLE_SECONDS"
  for p in $spin_cand; do
    tk="na"; io="na"
    if [ -r "/proc/$p/stat" ]; then tk="$(sed 's/.*) //' "/proc/$p/stat" 2>/dev/null | awk '{print $12 + $13}')"; fi
    if [ -r "/proc/$p/io" ]; then io="$(awk '/^rchar:|^wchar:/ {s += $2} END {print s + 0}' "/proc/$p/io" 2>/dev/null)"; fi
    echo "t1 $p ${tk:-na} ${io:-na}"
  done
fi
echo "[end]"
exit 0
