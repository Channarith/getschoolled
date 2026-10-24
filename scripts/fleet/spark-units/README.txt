SPARK SERVICES (systemd user units) UNDER VERSION CONTROL
==========================================================
Plain text on purpose (repo no-markdown house rule). Companion to docs/fleet-ops.txt.

WHAT IS HERE
  units/*.service          unit templates; @ROOT@ is replaced with the worktree the units run from
  units/*.service.d/*.conf drop-ins
  install.sh               dry run by default; --apply writes, backs up and never restarts anything
  lib.sh                   shared loop helpers: children in their own process group, interruptible sleeps, clean stop
  llm-forever.sh           STEM QLoRA loop; honors the hold file ~/.gs-hold/stem-train
  voice-forever.sh         Khmer CosyVoice fine-tune loop; honors hold-voice-train
  voice-ingest-forever.sh  CosyVoice voice-data ingest; GPU ASR only when the CUDA policy passes
  gpu-balance-monitor.sh   launcher for aoep_shared/spark_balance.py (the monitor's logic and tests)
  llama-warm.sh            wake the llama-server and load its model before the bake-off (hooked into spark_nightly.sh)
  enroll-ui.sh / aoep-enroll-ui.service     voice enrollment page, 127.0.0.1:8780, MemoryMax 2G, Restart=always
  listening-lab.sh / aoep-listening-lab.service   voice listening lab, 127.0.0.1:8790, serves the newest runs/*-clones
  uninstall.sh             removes the two lab units (dry run by default; training units only when named)
  translate-forever.sh     LEGACY v1 CPU translation loop; refuses to run unless AOEP_LEGACY_TRANSLATE=1

HOW THE LOOPS BEHAVE
  - One child at a time, in its own process group. SIGTERM/SIGINT to the loop terminates that whole group, waits
    AOEP_STOP_GRACE_S (20 s), then SIGKILLs: no orphans. The loop then exits with status 0, so systemd
    (Restart=always) does not treat a stop as a crash. Sleeps are interruptible.
  - Pausing the STEM loop: create ~/.gs-hold/stem-train (text is logged once). The running cycle finishes; no new
    one starts; delete the file to resume. A frozen loop (kill -STOP PID) also pauses it, but survives no reboot.
  - Test hook: AOEP_FOREVER_ONCE=1 makes any loop stop after one iteration.
  - Overrides without editing a unit: ~/.config/aoep/spark-units.env (VAR=value lines; every unit reads it).

THE GPU LOCK, PRIORITIES AND THE DEMO LABS (scripts/gs_run.sh, scripts/fleet/spark_gate.sh)
  Problems this fixes: a stuck nightly step held ~/.gs-gpu.lock for hours at 0% GPU; the same clone job queued three
  times behind it; a hand-started 3-worker ingest took 70 GB of the shared pool so every job refused to start.
  - One job per --name: a second gs_run.sh with the same name exits 75 at once and names the first.
  - Waiting is interruptible (non-blocking flock polled every 2 s), so TERM to a queued job works immediately.
  - --priority interactive (default) or background. Background jobs get an idle watchdog: no CPU in the process tree
    AND GPU 0% for --idle-timeout seconds (default 1800) stops the job (exit 125) and frees the lock. The nightly
    bake-off runs under gs_stage with BAKEOFF_TIMEOUT_MIN (90) and BAKEOFF_IDLE_S (1200).
  - An interactive job that has waited GS_PREEMPT_AFTER seconds (900; --preempt-after) for the lock sends TERM, then KILL
    after GS_PREEMPT_GRACE_S (60), to a BACKGROUND holder registered in ~/.gs-gpu.lock.owner (gs_run.sh and
    spark_nightly.sh both register). It never preempts an interactive holder.
  - Hand-run ingest: cosyvoice_batch_ingest.py refuses --workers above AOEP_INGEST_MAX_WORKERS (default 1) unless
    AOEP_INGEST_FORCE=1.
  - Status: scripts/fleet_status.sh ends with four lines for the Spark (GPU lock holder and age, memory against the 16 GB
    gate, lab ports, queued waiters); the same lines alone: bash scripts/fleet/spark_gate.sh. --no-gate hides them.
  Labs: install.sh writes both lab units (never enables or starts them). To run them:
    scripts/fleet/spark-units/install.sh --root <worktree> --apply --enable aoep-enroll-ui --enable aoep-listening-lab
    systemctl --user start aoep-enroll-ui aoep-listening-lab
  then from the laptop: ssh -N -L 8780:127.0.0.1:8780 -L 8790:127.0.0.1:8790 nvidia@192.168.1.107
  Settings (no unit edit): ~/.config/aoep/spark-units.env with AOEP_LAB_OUT, AOEP_VOICES_DIR, AOEP_VENV.

THE BALANCE MONITOR (aoep_shared/spark_balance.py)
  Jobs: (1) pause yt-dlp with SIGSTOP when MemAvailable is low and continue it when memory recovers;
        (2) stop the bake-off client only when it is demonstrably starved by a fine-tune AND memory is short.
  Facts it uses, from command lines (never GPU memory size, which the GB10 does not report):
        fine-tune   run_finetune.py, train.py, spark_cosyvoice*train*
        evaluation  evaluate.py            (never a reason to stop the bake-off, except an emergency)
        bake-off    spark_serve_eval.py, nightly_candidates.py, rag_small_evals.py   (BALANCE_BAKEOFF_PATTERN)
        llama-server state from HTTP only: /props (is_sleeping), /health (200 ok, 503 loading), /slots (decode count).
  Rules: no judgement until the server is ready; 600 s grace after every wake; the rate window starts at the FIRST
        decoded token and runs 180 s; starved = under 0.25 tokens/s over the window; a kill during a fine-tune also
        needs free memory under 24 GB; under 6 GB it may stop the bake-off even during an evaluation.
  Every threshold is an environment variable: BALANCE_FREE_LOW_MB (10240) BALANCE_FREE_OK_MB (16384)
        BALANCE_KILL_FLOOR_MB (24576) BALANCE_CRITICAL_MB (6144) BALANCE_WINDOW_S (180) BALANCE_STARVE_TOK_S (0.25)
        BALANCE_GRACE_S (600) BALANCE_TICK_S (20) BALANCE_LLAMA_URL BALANCE_BAKEOFF_PATTERN BALANCE_INGEST_PATTERN.
  Files (in ~/.local/share/aoep-train, override with BALANCE_DIR):
        balance.jsonl           one JSON object per line (event, reason, numbers), rotated at 5 MB x 5
        balance.status.json     latest sample, written atomically;  balance.status  the old key=value line
        balance.paused.json     processes it stopped (pid + start time), so a crash cannot strand them; a reused
                                PID is never continued
  Exit: SIGTERM resumes everything it stopped before it exits (the unit gives it 20 s). Never leaves a process stopped.
  One-off look: BALANCE_DIR=/tmp/b python3 -m aoep_shared.spark_balance --once   (acts once and exits; with
        PYTHONPATH=<worktree>/packages/shared/src)

THE LLAMA-SERVER SLEEP SETTING (not changed by this repo)
  The 35B Qwen server (snap qwen3-6.server, port 8342) runs with --sleep-idle-seconds 600 --fit-ctx 4096 --no-warmup.
  After 10 idle minutes it unloads its ~20 GB model; the next request reloads it ("fitting params to device
  memory ..."). The repo does not edit the snap. llama-warm.sh pays the reload before the bake-off instead.
  The machine has 121 GB of unified memory, so keeping the model resident is affordable. What YOU can do:
    - find where the flag is set (needs sudo; the exact snap config key is NOT verified here, so look before you edit):
        sudo snap get qwen3-6 -d
        snap info qwen3-6
        sudo systemctl cat snap.qwen3-6.server.service
        sudo journalctl -u snap.qwen3-6.server.service --no-pager | grep -iE "sleep|offload|layers|fit" | tail
    - if the snap exposes a setting for the idle timeout, raise it (for example to 7200) or turn it off while a bake-off
      can run; if the flag is baked into the snap's wrapper script, ask the snap's publisher or run your own
      llama-server unit instead of the snap.
    - verify GPU offload in that journal: it prints how many layers went to the GPU. If it says 0, the model is on
      the CPU and decoding will be slow no matter what the monitor does.
  Recommendation: leave the server asleep except while a bake-off runs (llama-warm.sh wakes it), or keep it resident.

ASR BURSTS AND THE GPU LOCK
  The ingest runs for days and uses the GPU for seconds at a time, so it cannot hold ~/.gs-gpu.lock for its life. Each
  ASR call takes the lock for the burst (aoep_shared/gpu_lock.py): wait AOEP_GPU_BURST_WAIT_S (20 s); if it is still
  busy, proceed WITHOUT it and do not wait again for AOEP_GPU_BURST_BACKOFF_S (300 s), so a training job holding the
  lock for hours costs the ingest one 20 s wait, not 20 s per segment. AOEP_GPU_BURST_LOCK=0 turns it off. No-op when
  GS_GPU_LOCK_HELD=1 (gs_run.sh and spark_nightly.sh set it). This is "take turns when you can", not a hard guarantee:
  the hard one-GPU-job rule still applies to everything started through scripts/gs_run.sh --gpu.

INSTALL (summary; the full steps are in docs/fleet-ops.txt, "SPARK SERVICES UNDER VERSION CONTROL")
  cd ~/code/getschoolled && git fetch -q origin
  git worktree add -f ~/code/gs-wt/main-$(date +%Y%m%d) origin/main
  ln -sfn ~/code/gs-wt/main-$(date +%Y%m%d) ~/code/gs-wt/main-current
  ~/code/gs-wt/main-current/scripts/fleet/spark-units/install.sh --root ~/code/gs-wt/main-current          # dry run
  ~/code/gs-wt/main-current/scripts/fleet/spark-units/install.sh --root ~/code/gs-wt/main-current --apply
  systemctl --user restart aoep-gpu-balance.service
  Never switch ~/code/getschoolled (the main checkout): it is on a feature branch with jobs running from it.
