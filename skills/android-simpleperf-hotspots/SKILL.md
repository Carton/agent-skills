---
name: android-simpleperf-hotspots
description: Record and analyze Android CPU hotspots and load with simpleperf, or investigate existing simpleperf/perf perf.data files offline. Use for hot processes/threads/functions, CPU spikes, instruction or cycle workload, and CPU performance comparisons. Distinguish CPU execution from scheduling, blocking, and GPU latency when diagnosing broader performance issues.
---

# Simpleperf CPU Hotspots and Load

Find the process, thread, and execution path that explains the reported CPU symptom.
Use measured event counts and relevant time windows; distinguish a hotspot from a
demonstrated cause of latency. Works with Android apps, native programs, and system
services. An existing recording needs neither adb nor the original device.

## Choose the workflow

- **Existing perf.data:** start with [offline analysis](references/analysis.md).
  Discover the recorded event, scope, clock, and data quality before interpreting it.
  Linux perf recordings may lack Android/simpleperf metadata; try supported host
  tools and describe missing capabilities rather than requiring a new capture.
- **New recording:** read [recording](references/recording.md). Discover device
  privileges and events; select app, PID/TID, or system scope to match the question.
- **A/B change or load comparison:** also read [comparisons](references/comparisons.md).
  Separate CPU time, executed work, and execution efficiency.
- **Hot syscall or suspected IPC/polling loop:** after identifying its PID/TID,
  read [syscall follow-up](references/syscalls.md).

Start with available evidence. Ask for a missing target, reproduction, or comparison
definition only when it changes the measurement. Do not require a connected device
for offline work or assume a package from the repository containing this skill.

## Select the measurement

| Question | Useful measurement | Interpretation boundary |
| --- | --- | --- |
| Where does CPU execution time go? | `record -e cpu-clock` or `task-clock`, with stacks | Sampled time attribution; percentages are relative to the included samples |
| What consumes CPU cycles? | `record -e cpu-cycles`, with stacks | Cycle-weighted attribution; frequency and CPU placement affect it |
| How much CPU time does a process use? | `stat -e task-clock -p PID` | Scheduled CPU time; normalize by elapsed time and state the utilization convention |
| Does a change execute more work? | `stat -e instructions`, plus `record -e instructions` for attribution | Retired instructions, not CPU utilization, latency, or power |
| Is the whole device affected? | System-wide capture/counters plus process attribution | Include app helpers, services, background work, and idle explicitly |
| Why is a frame/request slow despite little CPU? | Scheduling/wait trace, e.g. Perfetto; optionally supported `--trace-offcpu` | Ordinary CPU samples do not measure blocked time, runnable delay, or GPU execution |

Choose events supported by the device. `cpu-clock` is a useful initial time-based
hotspot event; it is not mandatory when another event better answers the question.
Use `stat` for counter totals and `record` for sampled attribution. `record` event
counts sum sampled periods and need not equal independently measured `stat` totals.
System-wide `instructions` is useful for device-work comparisons, not a universal
requirement for every app investigation.

## Locate tools once

Prefer a working official NDK/AOSP simpleperf distribution. Discover candidates
under the configured Android SDK/NDK and check the required executables; the highest
version directory may not contain simpleperf. Select the host OS/architecture binary
and keep Python scripts with their matching `libsimpleperf_report` runtime.

Define these task variables using discovered paths:

```sh
SP_ROOT=/absolute/path/to/ndk/simpleperf
SP="$SP_ROOT/bin/linux/x86_64/simpleperf"  # Adjust for host OS/architecture.
PYTHON=/absolute/path/to/python           # Use the project's .venv when present.
PERF=/absolute/path/to/perf.data
EVIDENCE=/absolute/path/to/new/evidence-directory
mkdir -p "$EVIDENCE"
"$SP" report --help
"$PYTHON" "$SP_ROOT/report_html.py" --help
```

Do not download or build tools when an installed distribution can read the data.
A custom report generator is optional unless the user or local project requires it.
If HTML support is missing, continue text analysis and report the limitation.
Preserve source recordings; write generated artifacts to a distinct task directory.

## Evidence and interpretation

1. Verify recording scope, event/modifiers, command, capture phase, and quality.
   Missing metadata stays unknown; a filename is not proof of workload or build.
2. Inspect broad process attribution, then relevant threads, DSOs, self cost, and
   inclusive call paths. PID alone aggregates a process; `comm` is a thread name.
3. For spikes/startup, inspect the symptom window. An aggregate flamegraph can hide
   bursts and does not show wall-time ordering. Align clocks before using logs.
4. Follow callers to a useful action point. Framework dispatch or a hot server may
   be an intermediate path; establish the requesting work before blaming it.
5. Mark uncertain symbols, truncated stacks, missing phases, and alternative
   explanations. On-CPU samples in a syscall do not prove blocking duration; render
   submission stacks do not prove a GPU bottleneck.

Weight attribution by the recorded event (`sample.period` when parsing with
`simpleperf_report_lib.py`), not the number of samples. Keep events separate.
`Self` is exclusive; `Children` is inclusive and must not be summed across frames.
Filtered reports can change the percentage denominator. System-wide PID 0/swapper
samples may represent idle; do not classify them as application CPU usage.

## Deliver the result

State the finding first, supported by the event/count or share, process/thread,
actionable stack, and capture window. Include the raw input and report paths,
relevant scope/commands, normalization and percentage denominator. For comparisons,
give absolute values/rates and deltas before explaining changed hotspot shares.

Separate observations from hypotheses and identify the smallest next measurement
or source inspection that would resolve a material gap. Do not change application
code based only on a familiar function name or unexplained aggregate percentage.
