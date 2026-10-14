# CPU Load and Performance Comparisons

## Define the metric before capturing

CPU utilization, instruction workload, cycle cost, and end-to-end latency answer
different questions. Choose the primary metric from the reported symptom. Use
sampling to attribute it; use counters or scheduled CPU-time evidence to quantify
it. A higher hotspot percentage can reflect reduced work elsewhere.

| Metric | Normalization | Caveat |
| --- | --- | --- |
| Process `task-clock` | CPU time / elapsed time = average cores used | Multiply by 100 for percent of one core; can exceed 100%. Device-capacity percent additionally divides by the stated core count |
| `instructions` | count / elapsed time, or / completed operations/frames | Workload volume, not utilization; higher throughput can legitimately increase instructions/s |
| `cpu-cycles` | count / elapsed time, or / completed work | DVFS and different cores change cycle counts and execution efficiency |
| IPC | instructions / cycles in compatible scope/window | Prefer grouped counters; do not combine totals from unmatched runs or scopes |
| Latency/FPS | Independent request/frame timing | CPU samples alone cannot establish frame deadlines, waiting, GPU time, or power |

Do not compute busy device utilization from a raw system-wide `cpu-clock` sample
sum: PID 0/idle can be included. Use scheduled running time excluding idle or
documented `/proc/stat` deltas for whole-device utilization. Include iowait/idle
definitions when they affect the interpretation.

## Counter examples

Use the recording reference's discovered `ADB` and `DEVICE_SP`, and selected
`TARGET_PIDS`/`DURATION`. Check device help and event support first:

```sh
"$ADB" shell "$DEVICE_SP" stat -p "$TARGET_PIDS" \
  -e task-clock --duration "$DURATION" > "$EVIDENCE/cpu-time.txt" 2>&1
"$ADB" shell "$DEVICE_SP" stat -p "$TARGET_PIDS" \
  --group instructions,cpu-cycles --duration "$DURATION" \
  > "$EVIDENCE/work-counters.txt" 2>&1
```

These are sequential windows; only derive ratios from events in the same window.
For whole-device effects, use `-a` instead of `-p` when permitted, retain per-process
attribution from a corresponding `record`, and describe idle/background/profiler
contributions. Targeted `stat -p` is valid for process CPU-time or work comparisons;
it can miss work delegated to other processes.

Inspect event running/enabled time or multiplexing percentages. Grouped events
must fit available PMU counters; if scheduling fails, reduce the event set.
Low running fractions/scaled counters reduce confidence. Events may differ across
CPU clusters; do not substitute an unsupported PMU event or combine incompatible
user/kernel modifiers without stating the change.

For periodic load, supported `stat --interval 1000 --interval-only-values` can
show per-second increments. Without `--interval-only-values`, interval values are
normally cumulative. Match the interval window to the symptom and keep capture
overhead consistent. Use stacks in the same phase for attribution, not an unrelated
busy section.

## Match the experiment

For new captures, hold event/modifiers, scope, sampling settings, device, build
conditions, scenario, input, and phase constant. Prefer equal-duration windows.
Record actual elapsed time, completed work, warmup/JIT state, thermal/frequency
conditions, background activity, and logging. When possible, repeat/interleave
A/B runs to distinguish a change from drift; a single pair has limited confidence.

If duration differs, raw counts are not directly comparable. Rates can be useful
for equivalent steady phases with trustworthy elapsed time; use work-normalized
counts when throughput differs. Variable startup phases need completion/latency
context, not just counts divided by requested duration. Never silently truncate
each run to a different phase to equalize data size.

For existing files, evaluate comparability before calculating deltas. Different
events (e.g. `cpu-clock` versus `instructions`) cannot produce a shared load delta.
Different scopes need an explicitly justified common subset, and filtering cannot
recover processes or time windows absent from one recording. PID numbers often
change between runs; match roles/builds and thread semantics rather than numbers.

## Report absolute values before shares

Include A/B count or time, actual duration or completed work, normalized metric,
absolute change, relative change when the baseline is nonzero, and repetition
range when available. Label `record` period sums as sampled attribution rather
than exact `stat` totals. Compare per-process self event totals without summing
inclusive callchain nodes.

A fraction rising from 10% to 20% does not prove doubled CPU cost. Check its absolute
count/rate and the denominator. If a material comparability field is unknown,
describe each file's hotspots separately and specify the matched measurement
needed to test a regression claim.

Official reference: [executable commands](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/doc/executable_commands_reference.md).
