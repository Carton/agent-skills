# Recording on Android

## Discover the environment

Use the host tool variables defined in `SKILL.md`. Also select `ADB` as an absolute
path to the appropriate host adb binary, `DEVICE_SP` as the discovered device
simpleperf path, `PKG` if profiling an app, and a unique device output filename.
Follow local device conventions; root is not a general prerequisite.

```sh
"$ADB" devices -l
# Set ANDROID_SERIAL when there are multiple devices; official scripts honor it too.
"$ADB" shell id
"$ADB" shell getprop ro.product.cpu.abi
"$ADB" shell getprop ro.build.fingerprint
"$ADB" shell command -v simpleperf
"$ADB" shell "$DEVICE_SP" list
"$ADB" shell "$DEVICE_SP" record --help
"$ADB" shell "$DEVICE_SP" stat --help
"$ADB" shell pidof "$PKG"
"$ADB" shell ps -A
```

Save the target process/thread identities, build, scene, input, warm/cold state,
duration, and commands in the evidence directory. Include secondary app processes
and cooperating services when they perform the work. Names can be truncated or
changed; verify `/proc/PID/cmdline` and `/proc/PID/task/TID/comm` where accessible.

For direct attachment, inspect privileges and actual tool errors. An app on a
non-root device generally needs to be debuggable or, on Android 10+, profileable
from shell. Release behavior is best measured with an optimized profileable build;
debug builds can change JNI, ART, and native optimization costs. Do not silently
rebuild, compile Java ahead of time, switch adb privileges, or alter security
settings to make a capture work.

If simpleperf is absent, use the matching NDK binary for the device ABI, staged to
a unique directory under `/data/local/tmp`, or the official app profiler below.
An executable may be blocked by device policy; report the actual restriction and
available profiling route instead of retrying privileged commands blindly.

## Choose scope and duration

- `-p PID1,PID2` for known processes; `-t TID1,TID2` for focused thread follow-up.
- `-a` for unexplained system load or cross-process work when privileges permit.
  Use `--exclude-perf` with `record` to exclude the simpleperf process's samples;
  other collection overhead still exists.
- Package-based capture for startup or process turnover. A fixed PID may miss a
  restarted process or independent app process. Check which processes were recorded.

A 10-second capture at `-f 400` is a reasonable starting point for steady hotspots,
not a fixed limit. Cover at least the symptom period for intermittent problems.
For long windows, reduce frequency, scope, or stack overhead rather than repeatedly
shortening the window until the symptom disappears. Existing captures should be
analyzed even if they use different parameters.

## Capture a running process

After selecting the target and confirming the options in device help:

```sh
DEVICE_PERF=/data/local/tmp/simpleperf-UNIQUE.data
"$ADB" shell "$DEVICE_SP" record \
  -p "$TARGET_PIDS" -e cpu-clock -f 400 \
  --call-graph dwarf --post-unwind=yes --duration 10 \
  -o "$DEVICE_PERF" > "$EVIDENCE/record.log" 2>&1
"$ADB" pull "$DEVICE_PERF" "$EVIDENCE/perf.data"
```

For a system-wide investigation, replace `-p "$TARGET_PIDS"` with
`-a --exclude-perf`. For cycle or instruction attribution, select the corresponding
supported event; retain identical scope and modifiers across new comparison runs.
Counter-only measurements do not need DWARF stacks; see `comparisons.md`.

`--post-unwind=yes` moves unwinding after collection, but stack copying and output
still have overhead. Frame-pointer unwinding (`--call-graph fp`) is cheaper when
the relevant binaries preserve frame pointers. Do not trade away usable stacks
without checking the result. Record log output, including loss/truncation warnings.

Prefer the default supported monotonic clock for new recordings. Use
`--clockid realtime` only when epoch alignment is required and supported, and
document it. Never assume logcat, Perfetto, and simpleperf use the same clock.

## App capture without assuming root

The official `app_profiler.py` handles device staging, app context, and pulling
data/binaries. Use the selected adb directory in this command's `PATH`; select a
device via `ANDROID_SERIAL`. Run it from the evidence directory because it creates
`binary_cache` there. The example below assumes adb is already non-root.

```sh
cd "$EVIDENCE"
"$PYTHON" "$SP_ROOT/app_profiler.py" -p "$PKG" --disable_adb_root \
  -r "-e cpu-clock -f 400 -g --duration 10" -o "$EVIDENCE/perf.data"
```

Read this installed script's `--help` and privilege behavior first. Without
`--disable_adb_root`, some versions try `adb root`; with it, some versions call
`adb unroot` if the shell is already root. The flag is not a general promise to
preserve adb state. On an already-root shell, prefer direct recording when current
privileges must be preserved. An opaque non-profileable release app on a non-root
device may not be capturable through this route.

For an explicitly requested startup capture, use its `--launch` or `-a ACTIVITY`
mode, which starts/restarts the app. Define cold versus warm startup and preserve
the same startup conditions across runs. Without a requested restart, attach to
the current workload. Verify startup was inside the recorded window.

## Supporting evidence and capture quality

Capture `top -H` or `/proc` CPU deltas only when useful to map hot threads or provide
CPU-time context. Bound the capture, document its overhead, and check this device's
`top` options. For logs, use a bounded time range or save available logcat with
timestamps; preserve existing buffers instead of clearing logcat or frame history.

Check actual duration, samples lost, stack truncation, process lifetime, and whether
the intended scenario ran. Fix demonstrated buffer overflow with lower frequency,
narrower scope, or suitable buffers. Preserve the failed capture/log and name each
retry distinctly. If the target restarts unexpectedly or a comparison phase changes,
mark that run as unmatched; a restart can be valid when it is the target symptom.

Pull raw data before relying on host reports. When possible, retain matching native
binaries, Java mappings, and JIT information before the device/build changes. Reuse
the same collection/logging settings for comparisons, and record any fallback event.

Official reference: [Android application profiling](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/doc/android_application_profiling.md).
