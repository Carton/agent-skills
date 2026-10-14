# Offline Analysis

Use `SP_ROOT`, `SP`, `PYTHON`, `PERF`, and `EVIDENCE` from `SKILL.md`. Start with the
original file; a device is only needed for optional collection of missing binaries.

## Inspect before interpreting

```sh
"$SP" dump --dump-feature meta_info -i "$PERF" > "$EVIDENCE/metadata.txt"
"$SP" report -i "$PERF" --sort pid --print-event-count \
  -o "$EVIDENCE/processes.txt" 2> "$EVIDENCE/report-warnings.txt"
"$SP" report -i "$PERF" --sort pid,tid,comm --print-event-count \
  -o "$EVIDENCE/threads.txt" 2>> "$EVIDENCE/report-warnings.txt"
"$SP" report -i "$PERF" --sort dso,symbol --print-event-count \
  -o "$EVIDENCE/symbols.txt" 2>> "$EVIDENCE/report-warnings.txt"
```

Read the metadata and report headers: recorded command, architecture, event and
modifiers, sample count, event count, system scope, clock, device/build, and loss
statistics (`record_stat`) when present. Metadata feature names/options vary; check
`dump --help` if this command fails. Successful empty metadata output means no such
feature was returned, not proof of zero loss. Linux perf files may lack these fields.
An unreadable file can need a newer host reader or Linux `perf report`; changing the
reader cannot create absent Android symbols or callchains.

Report requested `--duration` separately from known elapsed recording time.
First/last sample span is observed coverage, not an exact measurement interval;
samples omit idle gaps and startup/shutdown edges. Without trustworthy elapsed time,
do not invent instructions/s or utilization. Do not infer the recording date from
file mtime or directory name.

The process report groups by PID only. Adding `comm` would split it by thread name.
Use the thread report to map names to PID/TID; a hot thread name need not be the
process name. If a recording covers PID reuse, use timestamps/process lifetimes
rather than merging unrelated executions under a numeric ID.

For system-wide `cpu-clock`, total event count can include idle and span multiple
cores. Time-valued events use nanoseconds, but the sampled total is not automatically
busy CPU time. Inspect PID 0/swapper and idle kernel paths separately. `instructions`
and `cpu-cycles` use their own event units and also need scope interpretation.

## Drill into the responsible process/thread

Select `HOT_PID`/`HOT_TID` from the broad reports rather than a default package:

```sh
"$SP" report -i "$PERF" --pids "$HOT_PID" \
  --sort pid,tid,comm,dso,symbol --children --print-event-count \
  -o "$EVIDENCE/target-symbols.txt"
"$SP" report -i "$PERF" --tids "$HOT_TID" \
  -g --children --percent-limit 0.5 -o "$EVIDENCE/target-callgraph.txt"
```

`--percent-limit` limits displayed entries; lower it for a relevant small path.
Check for absent callchains, unresolved symbols, and failed/truncated unwinding
before trusting apparent leaf costs. A function can be expensive through its
callees while having little self cost. Follow an inclusive framework path to the
library/app work below it; do not add inclusive counts across frames.

Common clues are hypotheses until verified: UI traversal can lead to app drawing;
render-thread samples can show CPU submission; decoder stacks suggest image/media
work; GC/JIT samples suggest allocation/compilation; kernel or binder paths may
need cross-process follow-up. None establishes a cause merely by appearing.

## HTML and time windows

```sh
cd "$EVIDENCE"
"$PYTHON" "$SP_ROOT/report_html.py" -i "$PERF" \
  -o "$EVIDENCE/report.html" --no_browser
```

This supports overview, process/thread drilldown, and callchain flamegraphs when
stacks were recorded. Keep scripts, JS resources, and native report library from
the same distribution. Do not merge before/after files with multiple `-i` inputs
when the task requires a comparison; generate independent reports.

For bursts, convert to a chronological profile if the installed distribution has
`gecko_profile_generator.py`:

```sh
"$PYTHON" "$SP_ROOT/gecko_profile_generator.py" -i "$PERF" --remove-gaps 0 \
  > "$EVIDENCE/profile.json"
```

Open locally in Firefox Profiler or a compatible Perfetto UI. This conversion
shows sampled execution over time; it does not add scheduling, frame, or GPU
events. `--remove-gaps 0` preserves samples: some versions otherwise smooth broken
stack gaps by removing samples, changing attribution. It is optional when aggregate
attribution already answers the question.

To inspect a known symptom window, use `--filter-file` on compatible report tools.
Timestamps are absolute sample-clock nanoseconds, not offsets from capture start:

```text
CLOCK monotonic
GLOBAL_BEGIN <start_timestamp_ns>
GLOBAL_END <end_timestamp_ns>
```

Replace the placeholders with verified timestamps and match `CLOCK` to metadata
(e.g. `realtime` for a realtime recording). Supported clocks depend on the installed
reader. Inspect its sample-filter documentation for other clocks/options. Save the
filter, then add `--filter-file "$EVIDENCE/window.filter"` to the report command.
Use compatible log timestamps or a measured clock mapping for correlation.

## Missing symbols and callchains

Continue with trustworthy PID/TID/DSO attribution even when some binaries are
missing. State whether the unresolved region overlaps the suspected hotspot.

- Native: use unstripped binaries/debug symbols from the **recorded build and ABI**;
  verify build IDs. `--symfs` expects the recorded directory layout; `--symdir`
  searches binaries recursively where supported. Do not use current binaries just
  because their filenames match.
- On a matching accessible device, the official `binary_cache_builder.py -i PERF
  -lib SYMBOL_DIR` can build a cache. Run from the evidence directory and inspect
  its adb/root behavior first. Offline analysis must not depend on this step.
- The HTML script discovers `binary_cache` in its working directory. Add the
  matching `--proguard-mapping-file` for Java/Kotlin obfuscation; absent JIT metadata
  cannot generally be recovered from an unrelated later run.
- A capture without callchains can show symbol/DSO attribution but cannot produce
  a meaningful caller flamegraph. On-device reporting is an optional fallback
  only if the original device/binaries remain available.

If a custom parser is actually needed, use the installed
`simpleperf_report_lib.py`: accumulate `sample.period` separately per event and
filter, retain PID/TID/timestamp, and close the report library. Reuse built-in
grouped reports when they already provide the requested counts.

Official references: [view the profile](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/doc/view_the_profile.md),
[sample filtering](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/doc/sample_filter.md).
