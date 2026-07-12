# Android ANR (Application Not Responding) Debugging

## What is ANR?

ANR occurs when the UI thread of an Android app is blocked for too long:
- **Input timeout**: 5 seconds (no response to touch/key event)
- **Service timeout**: 20 seconds (service doesn't start)
- **Broadcast timeout**: 10 seconds (receiver slow)
- **ContentProvider timeout**: 10 seconds (provider slow)

## ANR Log Pattern

```
ANR in com.example.app (com.example.app/.MainActivity)
PID: 12345
Reason: Input dispatching timeout
```

## ANR Types and Triggers

### Type 1: Input Dispatching Timeout

**Cause:** Main thread blocked > 5 seconds

**Common blockers:**
- Network calls on main thread
- Heavy database operations
- Synchronous file I/O
- Complex calculations
- Lock contention

**Example log:**
```
ANR in com.example.app
PID: 12345
Reason: Input dispatching timeout
```

**Trace shows:**
```
"main" prio=5 tid=1 Blocked
  at java.lang.Object.wait(Object.java)
  - waiting on <0x1234> (a java.lang.Object)
  at java.lang.Thread.parkFor$(Thread.java:2120)
  at java.lang.Thread.sleep(Thread.java:...)
  at com.example.MainActivity.slowOperation(MainActivity.java:42)
```

### Type 2: Service Timeout

**Cause:** Service doesn't start in 20 seconds

**Common blockers:**
- Slow `onCreate()` or `onStartCommand()`
- Blocking operations in service initialization

**Example log:**
```
ANR in com.example.app
PID: 12345
Reason: Executing service com.example.app/.BackgroundService
```

### Type 3: Broadcast Timeout

**Cause:** BroadcastReceiver takes > 10 seconds

**Common blockers:**
- Heavy work in `onReceive()`
- No intent to start a Service for long work

**Example log:**
```
ANR in com.example.app
PID: 12345
Reason: Receiver not finishing
```

### Type 4: ContentProvider Timeout

**Cause:** ContentProvider slow to publish

**Common blockers:**
- Slow query in `query()`
- Heavy computation in provider

**Example log:**
```
ANR in com.example.app
PID: 12345
Reason: ContentProvider not responding
```

## Extracting ANR Traces

### Method 1: ADB Bugreport (Recommended)

```bash
# Generate bug report (includes ANR traces)
adb bugreport > bugreport.zip

# Unzip
unzip bugreport.zip

# Find ANR traces
# Location: bugreport/data/anr/traces.txt
cat bugreport/data/anr/traces.txt
```

### Method 2: Pull Directly (Root Required)

```bash
# Requires root
adb root
adb pull /data/anr/traces.txt
```

### Method 3: Developer Options

1. Settings → Developer Options
2. Enable "Take bug report"
3. Trigger ANR
4. Pull bug report from notification

## Reading ANR Traces

### Trace Structure

```
DALVIK THREADS (13):
"main" prio=5 tid=1 Blocked
  | group="main" sCount=1 dsCount=0 flags=1 obj=0x...
  | sysTid=12345 nice=0 cgrp=default sched=0/0 handle=0x...
  | state=S schedstat=( 0 0 0 ) utm=123 stm=45 core=1
  at com.example.SomeClass.blockingMethod(SomeClass.java:100)
  - waiting to lock <0x...> (a java.lang.Object), held by thread=15
  at com.example.MainActivity.onCreate(MainActivity.java:50)
  at android.app.Activity.performCreate(Activity.java:7000)
  ...
```

### Key Information

1. **Thread name**: Which thread is blocked (usually "main")
2. **Thread state**: `Blocked`, `Waiting`, `Sleeping`, `Runnable`
3. **Lock information**: What lock it's waiting for, who holds it
4. **Call stack**: Where it's blocked in code

### Thread States

| State | Meaning | Action |
|-------|---------|--------|
| Blocked | Waiting for a lock | Find lock holder, release it |
| Waiting | Waiting indefinitely | Check wait/notify/join |
| TimedWaiting | Waiting with timeout | Check sleep/wait(timeout) |
| Runnable | Runnable but not running | Check CPU contention |

## Common ANR Patterns and Fixes

### Pattern 1: Network on Main Thread

**Trace shows:**
```
"main" prio=5 tid=1 Blocked
  at java.net.SocketInputStream.socketRead0(SocketInputStream.java:-2)
  at java.net.SocketInputStream.read(SocketInputStream.java:...)
  at com.example.MainActivity.fetchData(MainActivity.java:42)
```

**Problem:** Synchronous network call on main thread

**Fix:**
```java
// WRONG
public void fetchData() {
    String result = new URL("https://api.example.com")
        .openStream().toString();
}

// CORRECT - Use AsyncTask/Coroutine/RxThread
public void fetchData() {
    new AsyncTask<Void, Void, String>() {
        protected String doInBackground(Void... voids) {
            return new URL("https://api.example.com")
                .openStream().toString();
        }
        protected void onPostExecute(String result) {
            updateUI(result);
        }
    }.execute();
}
```

### Pattern 2: Main Thread Deadlock

**Trace shows:**
```
"main" prio=5 tid=1 Blocked
  - waiting to lock <0x1234> (a java.lang.Object), held by tid=15

"Thread-15" prio=5 tid=15 Blocked
  - waiting to lock <0x5678> (a java.lang.Object), held by tid=1
```

**Problem:** Classic deadlock - main holds lock B, waits for lock A; thread 15 holds lock A, waits for lock B

**Fix:**
- Establish a global lock ordering
- Always acquire locks in the same order
- Use `tryLock()` with timeout
- Break into smaller critical sections

### Pattern 3: Heavy Database Operation

**Trace shows:**
```
"main" prio=5 tid=1 Native
  at android.database.sqlite.SQLiteConnection.nativeExecuteForCursorWindow(SQLiteConnection.java:-2)
  at android.database.sqlite.SQLiteConnection.executeForCursorWindow(SQLiteConnection.java:...)
  at com.example.MainActivity.loadFromDatabase(MainActivity.java:67)
```

**Problem:** Large query on main thread

**Fix:**
```java
// WRONG - Runs on main thread
Cursor cursor = db.query("large_table", null, null, null, null, null, null);

// CORRECT - Run on background thread
new Thread(() -> {
    Cursor cursor = db.query("large_table", null, null, null, null, null, null);
    List<Data> results = parseCursor(cursor);
    runOnUiThread(() -> updateUI(results));
}).start();
```

### Pattern 4: File I/O on Main Thread

**Trace shows:**
```
"main" prio=5 tid=1 Blocked
  at java.io.FileInputStream.readBytes(FileInputStream.java:-2)
  at java.io.FileInputStream.read(FileInputStream.java:...)
  at com.example.MainActivity.loadFile(MainActivity.java:89)
```

**Problem:** Synchronous file read on main thread

**Fix:**
```java
// WRONG
String content = new FileInputStream(file).toString();

// CORRECT
AsyncTask.execute(() -> {
    String content = new FileInputStream(file).toString();
    runOnUiThread(() -> updateUI(content));
});
```

### Pattern 5: Lock Contention

**Trace shows:**
```
"main" prio=5 tid=1 Blocked
  - waiting to lock <0x1234> (a java.lang.Object), held by tid=12
```

**Problem:** Main thread waiting on lock held by slow background thread

**Fix:**
- Minimize time holding locks
- Use concurrent collections (ConcurrentHashMap, CopyOnWriteArrayList)
- Use volatile instead of synchronized where possible
- Consider lock-free algorithms

## Debugging ANR Step-by-Step

### Step 1: Identify the Blocked Thread

```
grep -A 50 '"main"' traces.txt
```

Look for:
- Thread state (Blocked, Waiting, etc.)
- What it's waiting for (lock)
- Where in code it's blocked

### Step 2: Find the Lock Holder

```
grep -B 5 "held by" traces.txt
```

Identify which thread holds the lock that main is waiting for.

### Step 3: Analyze Both Threads

```
grep -A 30 '"Thread-XX"' traces.txt
```

Understand:
- What the lock holder is doing
- Why it's taking so long
- Whether it's deadlocked

### Step 4: Locate the Code

Match the call stack to your code:

```
at com.example.MainActivity.blockingMethod(MainActivity.java:42)
```

Open `MainActivity.java` line 42 and examine:
- What operation is performed
- Whether it should be on a background thread
- Whether locks are necessary

## Preventing ANR

### Best Practices

1. **Keep main thread light**
   - Only UI updates on main thread
   - All I/O in background
   - Minimal computation

2. **Use modern async tools**
   - Kotlin Coroutines (recommended)
   - RxJava
   - AsyncTask (legacy)

3. **Monitor main thread**
   ```java
   StrictMode.setThreadPolicy(new StrictMode.ThreadPolicy.Builder()
       .detectDiskReads()
       .detectDiskWrites()
       .detectNetwork()
       .penaltyLog()
       .build());
   ```

4. **Profile before release**
   - Use Android Studio Profiler
   - Check CPU usage
   - Look for janky frames

5. **Test on slow devices**
   - ANR happens more on low-end devices
   - Test with slow network
   - Test with large datasets

### Monitoring ANR

**Play Console:**
- ANR rate > 0.05% is concerning
- > 0.47% is critical (Google Play warning threshold)

**Firebase Performance Monitoring:**
- Tracks slow rendering
- Monitors main thread blocking
- ANR detection

**Custom ANR tracking:**
```java
public class AnrWatchDog extends Thread {
    public void run() {
        while (true) {
            long start = System.currentTimeMillis();
            // Post to main thread
            handler.post(() -> lastMainThreadTime = System.currentTimeMillis());
            // Sleep for 5 seconds
            Thread.sleep(5000);
            // If lastMainThreadTime wasn't updated, ANR occurred
            if (System.currentTimeMillis() - lastMainThreadTime > 5000) {
                Log.e("ANR", "Main thread blocked!");
            }
        }
    }
}
```

## ANR vs. Crash

| Aspect | ANR | Crash |
|--------|-----|-------|
| Trigger | Timeout | Exception |
| User sees | "App not responding" dialog | "App has stopped" dialog |
| Log location | traces.txt | logcat (FATAL EXCEPTION) |
| Common cause | Blocking main thread | Unhandled exception |
| Prevention | Background threads | Error handling |

Both can be caused by:
- OutOfMemoryError
- StackOverflowError
- Native crashes (SIGSEGV)

## Advanced Tools

### Systrace

```bash
python systrace.py --time=10 -o trace.html sched freq idle am wm gfx view binder_driver hal dalvik camera input res
```

Shows:
- CPU usage per thread
- Scheduling decisions
- Frame rendering times
- Identify blocked threads visually

### Perfetto

```bash
# Record trace
python record_trace.py -o trace.perfetto-trace -t 10s

# Open in https://ui.perfetto.dev
```

Modern replacement for Systrace with:
- Better UI
- More detailed traces
- Advanced filtering
