# Android Memory Leak Patterns

## Common Leak Patterns

### 1. Static Context Reference

**Pattern:**
```java
// WRONG
public class MyApp extends Application {
    private static Context context;
    @Override
    public void onCreate() {
        context = this;  // Leaks first Activity
    }
}
```

**Why it leaks:** The static `context` holds a reference to the Application context, which holds all Activities. Activities are never GC'd.

**Fix:**
```java
public class MyApp extends Application {
    private static Context context;
    @Override
    public void onCreate() {
        context = getApplicationContext();  // Use app context
    }
}
```

### 2. Handler Leak

**Pattern:**
```java
// WRONG
public class MainActivity extends Activity {
    private Handler handler = new Handler() {
        @Override
        public void handleMessage(Message msg) {
            // Implicit reference to outer Activity
        }
    };
}
```

**Why it leaks:** The Handler holds an implicit reference to the Activity. If there are pending messages in the queue, the Activity can't be GC'd.

**Fix:**
```java
public class MainActivity extends Activity {
    private static class SafeHandler extends Handler {
        private final WeakReference<MainActivity> activityRef;

        SafeHandler(MainActivity activity) {
            activityRef = new WeakReference<>(activity);
        }

        @Override
        public void handleMessage(Message msg) {
            MainActivity activity = activityRef.get();
            if (activity != null) {
                // Process message
            }
        }
    }

    private Handler handler = new SafeHandler(this);

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }
}
```

### 3. AsyncTask Leak

**Pattern:**
```java
// WRONG
public class MainActivity extends Activity {
    private AsyncTask<Void, Void, Void> task = new AsyncTask<Void, Void, Void>() {
        @Override
        protected Void doInBackground(Void... voids) {
            // Long-running operation
            return null;
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        task.execute();
    }
    // No cancellation in onDestroy()
}
```

**Why it leaks:** The AsyncTask holds a reference to the Activity. If the Activity is destroyed but the task is still running, it leaks.

**Fix:**
```java
public class MainActivity extends Activity {
    private AsyncTask<Void, Void, Void> task;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        task = new AsyncTask<Void, Void, Void>() {
            @Override
            protected Void doInBackground(Void... voids) {
                // Long-running operation
                return null;
            }
        }.execute();
    }

    @Override
    protected void onDestroy() {
        if (task != null && !task.isCancelled()) {
            task.cancel(true);
        }
        super.onDestroy();
    }
}
```

### 4. Singleton with Context

**Pattern:**
```java
// WRONG
public class DataManager {
    private static DataManager instance;
    private Context context;

    private DataManager(Context context) {
        this.context = context;  // Leaks context
    }

    public static DataManager getInstance(Context context) {
        if (instance == null) {
            instance = new DataManager(context);
        }
        return instance;
    }
}
```

**Why it leaks:** The singleton holds a Context. If it's an Activity context, it leaks.

**Fix:**
```java
public class DataManager {
    private static DataManager instance;
    private Context context;

    private DataManager(Context context) {
        this.context = context.getApplicationContext();  // Use app context
    }

    public static DataManager getInstance(Context context) {
        if (instance == null) {
            instance = new DataManager(context.getApplicationContext());
        }
        return instance;
    }
}
```

### 5. Anonymous Runnable Leak

**Pattern:**
```java
// WRONG
public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        handler.postDelayed(new Runnable() {
            @Override
            public void run() {
                // Implicit reference to Activity
            }
        }, 60000);  // 1 minute delay
    }
}
```

**Why it leaks:** The anonymous Runnable holds an implicit reference to the Activity.

**Fix:**
```java
public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        handler.postDelayed(new SafeRunnable(this), 60000);
    }

    private static class SafeRunnable implements Runnable {
        private final WeakReference<MainActivity> activityRef;

        SafeRunnable(MainActivity activity) {
            activityRef = new WeakReference<>(activity);
        }

        @Override
        public void run() {
            MainActivity activity = activityRef.get();
            if (activity != null) {
                // Do work
            }
        }
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }
}
```

### 6. Bitmap Leak (Pre-Android 3.0)

**Pattern:**
```java
// WRONG (Android 2.x)
Bitmap bitmap = BitmapFactory.decodeResource(getResources(), R.drawable.large_image);
imageView.setImageBitmap(bitmap);
// Bitmap not recycled
```

**Why it leaks:** On Android 2.x, Bitmap data was stored in native memory. Not recycling leaked native memory.

**Fix:**
```java
Bitmap bitmap = BitmapFactory.decodeResource(getResources(), R.drawable.large_image);
imageView.setImageBitmap(bitmap);

// When done (e.g., in onDestroy())
if (bitmap != null && !bitmap.isRecycled()) {
    bitmap.recycle();
    bitmap = null;
}
```

**Note:** On Android 3.0+, Bitmap data is managed by the GC, so explicit recycling is not necessary but can still help with memory pressure.

### 7. Listener Leak

**Pattern:**
```java
// WRONG
public class MainActivity extends Activity implements SomeManager.Listener {
    private SomeManager manager = SomeManager.getInstance();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        manager.setListener(this);  // Registers this Activity as listener
    }
    // Never unregisters
}
```

**Why it leaks:** The manager holds a reference to the Activity. Even when destroyed, the manager still references it.

**Fix:**
```java
public class MainActivity extends Activity implements SomeManager.Listener {
    private SomeManager manager = SomeManager.getInstance();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        manager.setListener(this);
    }

    @Override
    protected void onDestroy() {
        manager.removeListener(this);  // Unregister!
        super.onDestroy();
    }
}
```

### 8. Observable Leak (RxJava)

**Pattern:**
```java
// WRONG
public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Observable.interval(1, TimeUnit.SECONDS)
            .subscribe(tick -> {
                updateUI();  // Holds reference to Activity
            });
    }
}
```

**Why it leaks:** The Observable continues emitting and holds a reference to the Activity.

**Fix:**
```java
public class MainActivity extends Activity {
    private CompositeDisposable disposables = new CompositeDisposable();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        disposables.add(
            Observable.interval(1, TimeUnit.SECONDS)
                .subscribe(tick -> updateUI())
        );
    }

    @Override
    protected void onDestroy() {
        disposables.clear();  // Dispose all subscriptions
        super.onDestroy();
    }
}
```

## Detecting Leaks in Logcat

### gc_for_alloc Frequency Pattern

```bash
# Count GCs in last 5 minutes
grep -c "gc_for_alloc" logcat.log

# Show timing
grep "gc_for_alloc" logcat.log | awk '{print $1 " " $2}'
```

**Interpretation:**
- < 10/min: Normal
- 10-30/min: Moderate pressure, investigate
- > 30/min: Severe pressure, likely leak

### Activity Lifecycle Tracking

```bash
# Check if Activities are being destroyed
grep "ActivityManager: Displayed" logcat.log
```

If you see multiple `Displayed` logs for the same Activity without corresponding `onDestroy` calls, it's a leak.

### Heap Dump Analysis

```bash
# Capture heap dump
adb shell am dumpheap <pid> /data/local/tmp/heap.hprof
adb pull /data/local/tmp/heap.hprof

# Analyze with Android Studio or jhat
jhat -J-Xmx2g heap.hprof
# Open browser to localhost:7000
```

Look for:
- Multiple instances of the same Activity
- Objects that should be GC'd but aren't
- Reference chains from GC roots to leaked objects

## Tools for Leak Detection

### LeakCanary

**Setup:**
```gradle
dependencies {
    debugImplementation 'com.squareup.leakcanary:leakcanary-android:2.12'
}
```

LeakCanary automatically detects leaks and provides:
- Heap dump analysis
- Reference chain to GC root
- Leak cause hypothesis

### Android Studio Profiler

1. View → Tool Windows → Profiler
2. Select your app process
3. Click **Memory**
4. Click **Capture heap dump**
5. Analyze:
   - Find duplicate Activity instances
   - Inspect reference chains
   - Identify largest allocations

### StrictMode

```java
if (BuildConfig.DEBUG) {
    StrictMode.setVmPolicy(new StrictMode.VmPolicy.Builder()
        .detectLeakedSqlLiteObjects()
        .detectLeakedClosableObjects()
        .penaltyLog()
        .build());
}
```

## Prevention Best Practices

1. **Always use Application context** for singletons and long-lived objects
2. **Use WeakReference** for callbacks from long-running operations
3. **Unregister listeners** in `onDestroy()`
4. **Cancel async operations** in `onDestroy()`
5. **Avoid non-static inner classes** in Activities
6. **Use static inner classes** for Handlers, Runnables, etc.
7. **Dispose RxJava subscriptions** in `onDestroy()`
8. **Recycle Bitmaps** on older Android versions when no longer needed
