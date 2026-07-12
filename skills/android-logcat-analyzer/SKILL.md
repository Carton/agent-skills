---
name: android-logcat-analyzer
description: Analyze Android logcat logs to diagnose app crashes, ANRs (Application Not Responding), memory leaks, and performance issues. Use this skill whenever the user mentions analyzing Android app logs, logcat debugging, memory leak detection, ANR troubleshooting, or native crash analysis. Trigger on phrases like "app crashed", "Android logcat analysis", "OutOfMemoryError", "ANR debugging", "memory leak in Android", "native crash SIGSEGV", or "tombstone analysis". This skill covers generic Android app issues - for Android Windows emulator logs (Wine/Proton), use gamenative-log-analyzer instead.
compatibility: Requires adb for log collection, optional Android Studio for detailed memory profiling
---

# Android Logcat Analyzer

## Purpose

Analyze Android system logs (logcat) to diagnose:
- **Java crashes** (RuntimeException, NullPointerException, OutOfMemoryError)
- **Native crashes** (SIGSEGV, SIGABRT, tombstones)
- **ANR** (Application Not Responding)
- **Memory leaks** (gc_for_alloc patterns, Context leaks, Handler leaks)
- **Performance issues** (frame rate drops, stuttering, lag)

## When to Use This Skill

- App crashes with Java exceptions
- "Application not responding" dialog appears
- Memory leaks or OutOfMemoryError crashes
- Native code crashes (NDK, JNI)
- Performance degradation over time
- System kills app without obvious error

**For Android Windows emulator issues** (GameNative, Winlator, GameHub), use `gamenative-log-analyzer` skill instead.

## Log Sources

### Primary: logcat

**Collection methods:**

```bash
# Full logcat (all buffers)
adb logcat -d > logcat.log

# Last 5 minutes (approximate)
adb logcat -d -t 300000 > logcat.log

# Specific buffers
adb logcat -d -b main -b system -b crash > logcat.log

# Clear and reproduce
adb logcat -c
# ... trigger the issue ...
adb logcat -d > crash.logcat
```

**Timestamp format:** `MM-DD HH:MM:SS.mmm`

### Secondary Sources

- **ANR traces**: `/data/anr/traces.txt` (pull with `adb bugreport`)
- **Tombstones**: `/data/tombstones/tombstone_XX` (native crashes)
- **Application logs**: Custom file logging in your app
- **Bug reports**: `adb bugreport` (comprehensive, includes all above)

## Workflow

### 1. Time-Based Filtering (CRITICAL - 从后往前找策略)

**核心原则**：用户通常在崩溃后立即分析日志，所以应该从**最新的时间往回找**，而不是假设某个特定崩溃时间。

**⚠️ 常见错误**：不要假设bug报告中的时间就是当前问题！那可能是历史崩溃。

**正确的过滤策略：**

1. **找到最晚的时间戳**（从日志末尾开始）：
```bash
# logcat 最晚时间
tail -1 logcat.log | awk '{print $1 " " $2}'
```

2. **从最晚时间往回推 5 分钟**作为分析窗口

3. **如果这 5 分钟内没有找到问题**，逐步扩大窗口（10分钟、15分钟）

**时间窗口计算示例**：
```python
# 伪代码 - 从后往前找
latest_time = extract_latest_timestamp(logcat.log)  # 例如：15:06:33
window_start = latest_time - 5 minutes                 # 例如：15:01:33
window_end = latest_time + 10 seconds                   # 例如：15:06:43

# 过滤到这个窗口
filtered_logcat = filter_by_time(logcat.log, window_start, window_end)
```

### 2. Analyze by Priority

After time-filtering, search in priority order:

#### 🔴 P0 - Application Death (Highest Priority)

```bash
grep -E "app died|no saved state|Process.*died|Force removing" filtered_logcat
```

**What to look for:**
- `ProcessRecord: app died, no saved state`
- `Force removing ActivityRecord: app has stopped`
- `Killing: pid: xxxx uid: u0_axxx`
- `ActivityManager: No process killed for`

#### 🔴 P0 - System Kill Signals

```bash
grep -E "signal 9|signal 11|SIGKILL|SIGSEGV|SIGABRT|killed" filtered_logcat
```

**Signal types:**
| Signal | Meaning | Common Cause |
|--------|---------|--------------|
| SIGKILL (9) | Force killed by system | OOM, low memory killer, user force-quit |
| SIGSEGV (11) | Segmentation fault | Null pointer, invalid memory access |
| SIGABRT (6) | Abort called | Assertion failure, explicit abort |
| SIGBUS (7) | Bus error | Misaligned memory access |

#### 🔴 P1 - Java Fatal Exceptions

```bash
grep -E "FATAL EXCEPTION|AndroidRuntime: FATAL" filtered_logcat
```

**Key sections to extract:**
```
FATAL EXCEPTION: main
Process: com.example.app, PID: 12345
java.lang.NullPointerException: Attempt to invoke virtual method
    at com.example.MainActivity.onCreate(MainActivity.java:42)
```

#### 🔴 P1 - Native Crashes

```bash
grep -E "libc: Fatal signal|DEBUG: signal|tombstone" filtered_logcat
```

**Native crash analysis requires:**
- Check tombstone files: `adb pull /data/tombstones/tombstone_XX`
- Symbolize with `ndk-stack`: `ndk-stack -sym app/build/intermediates/merged_native_libs -dump logcat.txt`
- Look for signal number, fault address, and backtrace

#### 🟡 P2 - ANR (Application Not Responding)

```bash
grep -E "ANR in|Input dispatching timeout|Reason: executing service" filtered_logcat
```

**ANR types:**
- `Input dispatching timeout` - Main thread blocked > 5 seconds
- `Service timeout` - Service doesn't start/stop in time
- `Broadcast timeout` - Broadcast receiver takes too long
- `ContentProvider timeout` - ContentProvider slow to publish

**Get ANR traces:**
```bash
# Pull ANR file (requires root or adb bugreport)
adb bugreport > bugreport.zip
# Or if you have root:
adb pull /data/anr/traces.txt
```

#### 🟡 P2 - Memory Issues

```bash
# Memory pressure
grep -E "low.*memory|oom|gc_for_alloc" filtered_logcat

# OutOfMemoryError
grep -E "OutOfMemoryError" filtered_logcat
```

**See [Memory Analysis](#3-memory-state-analysis) section for detailed patterns.**

#### 🟡 P2 - Performance Issues

```bash
# Frame rate drops
grep -E "Skipped.*frame|buffer.*lag|fps.*drop" filtered_logcat

# Choreographer issues
grep -i "choreographer" filtered_logcat
```

### 3. Memory State Analysis

Memory issues rarely crash apps immediately - they cause gradual performance degradation.

#### 3.1 Memory Pressure Patterns

**gc_for_alloc frequency analysis:**

```bash
# Count gc_for_alloc in last 5 minutes
grep -c "gc_for_alloc" filtered_logcat

# Show timing pattern
grep "gc_for_alloc" filtered_logcat | awk '{print $1 " " $2}'
```

**Pattern interpretation:**
| Frequency | Meaning | Action |
|-----------|---------|--------|
| < 10/min | Normal | No action |
| 10-30/min | Moderate pressure | Monitor, check for memory leaks |
| > 30/min | Severe pressure | **Immediate action needed** |
| Continuous | OOM imminent | App will crash soon |

**Example pattern:**
```
03-27 15:01:20.123 12345 12345 I art: gc_for_alloc freestyle
03-27 15:01:20.456 12345 12345 I art: gc_for_alloc concurrent
03-27 15:01:20.789 12345 12345 I art: gc_for_alloc freestyle
# Three GCs in 666ms = severe memory pressure
```

#### 3.2 Low Memory Killer Behavior

```bash
# Check if system is killing your app
grep -E "lowmemorykiller: Killing|ActivityManager: Killing" filtered_logcat
```

**Adjacency levels (adj):**
| adj | Meaning | Likelihood of being killed |
|-----|---------|---------------------------|
| 0 | Foreground app | Very low |
| 1 | Visible app | Low |
| 2 | Perceptible app | Low-Medium |
| 3 | Backup app | Medium |
| 4 | Previous app | Medium-High |
| 5-8 | Home/Services | High |
| 9-15 | Cached background | Very high |

#### 3.3 Memory Leak Detection

**Common leak patterns in logcat:**

1. **Context leak:**
   - Activity not destroyed after `onDestroy()`
   - Look for: Activity still referenced after `onStop`

2. **Handler leak:**
   - Handler holding Activity reference
   - Look for: Handler messages still processing after Activity destroyed

3. **AsyncTask leak:**
   - AsyncTask not cancelled in `onDestroy()`
   - Look for: AsyncTask threads still running after Activity destroyed

4. **Static reference leak:**
   - Static field holding Activity reference
   - Look for: Activity instances never deallocated

**Leak indicators in logcat:**
```
# Activity never destroyed (no onDestroy log)
# ActivityManager: Displayed com.example.app/.MainActivity: 1,234 ms
# ... later ...
# ActivityManager: Displayed com.example.app/.MainActivity: 1,456 ms
# Multiple launches without destroys = leak

# Handler looper messages still active
# Handler: Sending message to a Handler on a dead thread
```

#### 3.4 OutOfMemoryError Analysis

```bash
# Find OOM crashes
grep -B 20 "OutOfMemoryError" filtered_logcat
```

**Key information to extract:**
- Which allocation type failed (bitmap, byte array, etc.)
- Available memory at crash time
- Largest allocations before crash

**Common OOM causes:**
1. Bitmaps not recycled (especially on large images)
2. Memory leaks over time
3. Large allocations without checking available memory
4. Memory fragmentation

#### 3.5 Memory Profiling Integration

When logcat analysis indicates memory issues, use Android Studio Profiler:

```bash
# Start profiling
adb shell am dumpheap <pid> /data/local/tmp/heap.hprof
adb pull /data/local/tmp/heap.hprof

# Or use Android Studio: View → Tool Windows → Profiler
# Select your app → Memory → Capture heap dump
```

### 4. ANR Analysis

#### 4.1 Identify ANR Type

**ANR log pattern:**
```
ANR in com.example.app (com.example.app/.MainActivity)
PID: 12345
Reason: Input dispatching timeout
```

**ANR types:**
| Type | Timeout | Trigger |
|------|---------|---------|
| Input timeout | 5 seconds | No response to touch/key event |
| Service timeout | 20 seconds | Service doesn't start |
| Broadcast timeout | 10 seconds | Broadcast receiver slow |
| ContentProvider timeout | 10 seconds | ContentProvider slow to publish |

#### 4.2 Extract ANR Traces

```bash
# From bug report
adb bugreport > bugreport.zip
unzip bugreport.zip
# ANR traces in: bugreport/data/anr/traces.txt

# Or pull directly (requires root)
adb root
adb pull /data/anr/traces.txt
```

#### 4.3 Read ANR Traces

**Key sections:**
```
"main" prio=5 tid=1 Blocked
  | group="main" sCount=1 dsCount=0 flags=1 obj=0x...
  | sysTid=12345 nice=0 cgrp=default sched=0/0 handle=0x...
  | state=S schedstat=( 0 0 0 ) utm=123 stm=45 core=1
  at com.example.SomeClass.blockingMethod(SomeClass.java:100)
  - waiting to lock <0x...>, held by thread 15
  at com.example.MainActivity.onCreate(MainActivity.java:50)
```

**What to look for:**
- Which thread is blocked
- What lock it's waiting for
- Which thread holds the lock
- Call stack showing why it blocked

**Common ANR causes:**
1. **Main thread blocking** - Network calls, database operations on main thread
2. **Deadlock** - Thread A holds lock 1, waits for lock 2; Thread B holds lock 2, waits for lock 1
3. **Slow operations** - Heavy computation on main thread
4. **Synchronization issues** - Waiting on locks held by slow threads

### 5. Native Crash Analysis

#### 5.1 Identify Native Crashes

**Logcat pattern:**
```
F/libc    (12345): Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
F/DEBUG    (12345): *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
F/DEBUG    (12345): Build fingerprint: '...'
F/DEBUG    (12345): Revision: '0'
F/DEBUG    (12345): pid: 12345, tid: 12345, name: example.app  >>> com.example.app <<<
F/DEBUG    (12345): signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
F/DEBUG    (12345):     x0  0000000000000000  x1  0000000000000001
F/DEBUG    (12345):     x2  0000000000000002  x3  0000000000000003
...
F/DEBUG    (12345): backtrace:
F/DEBUG    (12345):     #00 pc 00012345  /data/app/~~.../lib/arm64/libnative.so (native_function+123)
F/DEBUG    (12345):     #01 pc 00023456  /data/app/~~.../lib/arm64/libnative.so (java_com_example_MainActivity_nativeMethod+45)
...
F/DEBUG    (12345): Tombstone written to: /data/tombstones/tombstone_01
```

#### 5.2 Pull and Symbolize Tombstone

```bash
# Pull tombstone
adb pull /data/tombstones/tombstone_01

# Symbolize with ndk-stack (requires unstripped .so files)
adb logcat -d | ndk-stack -sym app/build/intermediates/merged_native_libs -dump -

# Or directly on tombstone
ndk-stack -sym app/build/intermediates/merged_native_libs tombstone_01
```

#### 5.3 Common Native Crash Causes

| Crash Pattern | Meaning | Fix |
|---------------|---------|-----|
| `fault addr 0x0` | Null pointer dereference | Check for null before accessing |
| `SEGV_ACCERR` | Permission error | Check file/mapping permissions |
| `SIGABRT` in `abort()` | Assertion failed | Find failed assertion |
| `SIGFPE` | Divide by zero | Check divisor != 0 |

### 6. Report Structure

**Always use this format:**

```markdown
# Android Logcat Analysis Report

## Executive Summary
[Brief 2-3 sentence overview of the main issue]

## Issue Analysis
**Timestamp**: [When issue occurred]
**Issue Type**: [Java crash / Native crash / ANR / Memory leak]
**Root Cause**: [What actually went wrong]

## Detailed Findings

### Crash/ANR Details
[Key findings from logcat, stack traces]

### Memory Analysis (if applicable)
[gc_for_alloc patterns, leak indicators, OOM history]

### Timeline
[Chronological sequence of events]

## Recommendations
1. [Actionable fix #1]
2. [Actionable fix #2]
3. [If applicable: Further debugging steps]

## Appendix
- Device: [Device info from logcat]
- Android Version: [From logcat]
- App Version: [From manifest or logcat]
- Analysis Time Window: [Start - End]
```

## Common Issues and Quick Fixes

### Memory Leak: Static Context Reference

**Symptoms:**
```
gc_for_alloc appears every few seconds
Activity instances never destroyed
Memory usage increases over time
```

**Fix:**
```java
// WRONG
public class MyApp extends Application {
    private static Context context;  // Leaks first Activity
    public void onCreate() {
        context = this;
    }
}

// CORRECT
public class MyApp extends Application {
    private static Context context;
    public void onCreate() {
        context = getApplicationContext();  // Use app context
    }
}
```

### ANR: Network on Main Thread

**Symptoms:**
```
ANR in com.example.app
Reason: Input dispatching timeout
Main thread blocked in java.net.SocketInputStream.socketRead0
```

**Fix:**
```java
// WRONG - Runs on main thread
public void fetchData() {
    String result = new URL("https://api.example.com").openStream().toString();
}

// CORRECT - Runs in background
public void fetchData() {
    new AsyncTask<Void, Void, String>() {
        protected String doInBackground(Void... voids) {
            return new URL("https://api.example.com").openStream().toString();
        }
    }.execute();
}
```

### Native Crash: JNI Null Pointer

**Symptoms:**
```
Fatal signal 11 (SIGSEGV), fault addr 0x0
Crash in JNI function calling Java method with null object
```

**Fix:**
```cpp
// WRONG
JNIEXPORT void JNICALL Java_com_example_MainActivity_nativeMethod(
    JNIEnv* env, jobject thiz, jobject data) {
    jclass cls = env->GetObjectClass(data);  // data might be null
}

// CORRECT
JNIEXPORT void JNICALL Java_com_example_MainActivity_nativeMethod(
    JNIEnv* env, jobject thiz, jobject data) {
    if (data == nullptr) {
        return;  // Check for null
    }
    jclass cls = env->GetObjectClass(data);
}
```

## Advanced Analysis Tools

### LeakCanary Integration

**Setup:**
```gradle
dependencies {
    debugImplementation 'com.squareup.leakcanary:leakcanary-android:2.12'
}
```

LeakCanary automatically:
- Detects Activity leaks
- Provides detailed leak traces
- Shows reference chains to GC roots

### StrictMode Detection

**Enable in Application.onCreate():**
```java
if (BuildConfig.DEBUG) {
    StrictMode.setThreadPolicy(new StrictMode.ThreadPolicy.Builder()
        .detectDiskReads()
        .detectDiskWrites()
        .detectNetwork()
        .penaltyLog()
        .build());
    StrictMode.setVmPolicy(new StrictMode.VmPolicy.Builder()
        .detectLeakedSqlLiteObjects()
        .detectLeakedClosableObjects()
        .penaltyLog()
        .build());
}
```

### Android Studio Profiler

For in-depth analysis:
1. Open Android Studio → View → Tool Windows → Profiler
2. Select your process
3. **CPU**: Profile method execution, find hotspots
4. **Memory**: Track allocations, find leaks, capture heap dumps
5. **Network**: Inspect API calls, latency
6. **Energy**: Check battery impact

## Integration with Other Skills

This skill focuses on **generic Android app issues**. For specialized scenarios:

- **`gamenative-log-analyzer`**: Android Windows emulator logs (GameNative, Winlator, GameHub)
  - Wine/Proton error patterns
  - X11 display server issues
  - Steam client errors
  - ARM translation layer problems

- **`core-dumps`**: Advanced native crash analysis with GDB
- **`sanitizers`**: Memory error detection during development (ASan, UBSan, TSan)
- **`valgrind`**: Memory profiling for native code (Linux development)

## Noise to Ignore

These messages are usually not relevant to app crashes:

- Repetitive Wifi errors (`WifiStaIfaceAidlImpl`)
- Background service messages (unless they're your app)
- Non-critical library init logs
- System-level messages unrelated to your app
- `MTK_APPList` status notifications (unless STATE_DEAD)

Focus on messages from your app package and its related processes.

## References

For detailed debugging techniques:
- [references/memory-leaks.md](references/memory-leaks.md) - Memory leak patterns and detection
- [references/anr-debugging.md](references/anr-debugging.md) - ANR troubleshooting guide
- [references/native-crashes.md](references/native-crashes.md) - Native crash and tombstone analysis
