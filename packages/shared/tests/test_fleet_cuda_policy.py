from aoep_shared.fleet_cuda_policy import analyze, parse, render

SPARK = """CUDA_POLICY_PROBE 1
host=Chans-Spark
cpus=20
gpu_util=0
proc=3261974|660.0|/home/nvidia/code/getschoolled/.venv/bin/python -m uvicorn speech_gw.main:app --port 8002|NLLB_DEVICE=cpu
proc=5186|680.0|llama-server --model /tmp/qwen.gguf|
proc=3068016|150.0|python3 scripts/cosyvoice_ingest.py --urls-file x|AOEP_ASR_DEVICE=cpu CUDA_VISIBLE_DEVICES=
proc=1|0.1|/sbin/init|
"""


def test_flags_cpu_pins_and_hidden_gpus():
    findings = analyze(parse(SPARK))
    texts = " | ".join(f.message for f in findings)
    assert "NLLB_DEVICE=cpu" in texts and "AOEP_ASR_DEVICE=cpu" in texts and "CUDA_VISIBLE_DEVICES is empty" in texts
    assert sum(f.severity == "CRIT" for f in findings) == 3


def test_flags_gpu_idle_while_cpu_bound():
    findings = analyze(parse(SPARK))
    warn = [f for f in findings if f.severity == "WARN"]
    assert len(warn) == 1 and "GPU is 0% busy" in warn[0].message and "1490%" in warn[0].message


def test_clean_host_has_no_findings():
    report = parse("CUDA_POLICY_PROBE 1\nhost=x\ncpus=8\ngpu_util=85\nproc=10|300.0|python train.py|\n")
    assert analyze(report) == []
    assert "OK" in render(report, [])


def test_no_gpu_means_no_idle_finding():
    report = parse("CUDA_POLICY_PROBE 1\nhost=mac\ngpu_util=none\nproc=10|900.0|python x.py|\n")
    assert analyze(report) == []
