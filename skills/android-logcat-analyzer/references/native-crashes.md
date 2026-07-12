# Android Native Crash Analysis

## Native Crash Overview

Native crashes occur in C/C++ code (NDK, JNI) and are signaled by:
- **SIGSEGV** (11): Segmentation fault - invalid memory access
- **SIGABRT** (6): Abort - assertion failure or explicit abort
- **SIGBUS** (7): Bus error - misaligned access
- **SIGFPE** (8): Floating point exception - divide by zero

## Logcat Pattern

```
F/libc    (12345): Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
F/DEBUG    (12345): *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
F/DEBUG    (12345): Build fingerprint: '...'
F/DEBUG    (12345): Revision: '0'
F/DEBUG    (12345): pid: 12345, tid: 12345, name: example.app  >>> com.example.app <<<
F/DEBUG    (12345): signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
F/DEBUG    (12345):     x0  0000000000000000  x1  0000000000000001
F/DEBUG    (12345):     x2  0000000000000002  x3  0000000000000003
F/DEBUG    (12345):     x4  0000000000000004  x5  0000000000000005
...
F/DEBUG    (12345): backtrace:
F/DEBUG    (12345):     #00 pc 00012345  /data/app/~~.../lib/arm64/libnative.so (native_function+123)
F/DEBUG    (12345):     #01 pc 00023456  /data/app/~~.../lib/arm64/libnative.so (java_com_example_MainActivity_nativeMethod+45)
F/DEBUG    (12345):     #02 pc 00345678  /system/lib64/libart.so (art_quick_generic_jni_trampoline+...)
...
F/DEBUG    (12345): Tombstone written to: /data/tombstones/tombstone_01
```

## Signal Types

| Signal | Code | Meaning | Common Cause |
|--------|------|---------|--------------|
| SIGSEGV | SEGV_MAPERR (1) | Address not mapped | Null pointer dereference |
| SIGSEGV | SEGV_ACCERR (2) | Access denied | Invalid permissions |
| SIGBUS | BUS_ADRALN (1) | Invalid address alignment | Misaligned struct access |
| SIGBUS | BUS_OBJERR (3) | Object error | Hardware error |
| SIGABRT | - | Abort called | Assertion failure |
| SIGFPE | FPE_INTDIV (1) | Integer divide by zero | Division by zero |
| SIGFPE | FPE_INTOVF (2) | Integer overflow | Overflow on signed int |

## Extracting Tombstones

### Method 1: Pull Direct (Root)

```bash
adb root
adb pull /data/tombstones/tombstone_XX
```

### Method 2: Bugreport

```bash
adb bugreport bugreport.zip
unzip bugreport.zip
# Tombstones in: bugreport/data/tombstones/
```

### Method 3: Logcat Only

```bash
# Capture logcat with native crash details
adb logcat -d | grep -A 50 "FATAL SIGNAL"
```

## Symbolizing with ndk-stack

**ndk-stack** translates addresses to function names.

### Prerequisites

You need unstripped native libraries:
```gradle
android {
    buildTypes {
        release {
            ndk {
                debugSymbolLevel 'FULL'  // Include symbols in release
            }
        }
    }
}
```

Or keep unstripped `.so` files separately:
```bash
# Find unstripped libs
find app/build -name "*.so" | grep obj
# app/build/intermediates/merged_native_libs/.../obj/arm64-v8a/libnative.so
```

### Symbolizing Logcat

```bash
# Pipe logcat to ndk-stack
adb logcat -d | ndk-stack -sym app/build/intermediates/merged_native_libs -dump -
```

### Symbolizing Tombstones

```bash
ndk-stack -sym app/build/intermediates/merged_native_libs tombstone_01
```

**Output:**
```
Stack frame 01: pc 00023456  /data/app/.../libnative.so (java_com_example_MainActivity_nativeMethod+45)
java_com_example_MainActivity_nativeMethod(JNIEnv*, jobject, jstring)
    /path/to/jni/native.cpp:42
```

## Common Crash Patterns

### Pattern 1: Null Pointer Dereference

**Symptoms:**
```
Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
```

**Cause:** Accessing address 0x0 (null pointer)

**Example (bad code):**
```cpp
JNIEXPORT void JNICALL Java_com_example_MainActivity_nativeMethod(
    JNIEnv* env, jobject thiz, jobject data) {
    jclass cls = env->GetObjectClass(data);  // data is null!
    // Crash here with fault addr 0x0
}
```

**Fix:**
```cpp
JNIEXPORT void JNICALL Java_com_example_MainActivity_nativeMethod(
    JNIEnv* env, jobject thiz, jobject data) {
    if (data == nullptr) {
        return;  // Check for null
    }
    jclass cls = env->GetObjectClass(data);
}
```

### Pattern 2: JNI Object Lifetime Issue

**Symptoms:**
```
Fatal signal 11 (SIGSEGV), fault addr 0x12345678
Crash when accessing JNI local/global ref
```

**Cause:** Using a JNI reference after it's invalidated

**Example (bad code):**
```cpp
jobject globalRef;

JNIEXPORT void JNICALL Java_com_example_MainActivity_init(JNIEnv* env, jobject thiz) {
    jobject localRef = ...;
    globalRef = env->NewGlobalRef(localRef);  // OK
    // localRef goes out of scope, but globalRef is valid
}

JNIEXPORT void JNICALL Java_com_example_MainActivity_use(JNIEnv* env, jobject thiz) {
    // If globalRef was deleted elsewhere, this crashes
    jclass cls = env->GetObjectClass(globalRef);
}
```

**Fix:**
```cpp
// Track reference lifecycle
jobject globalRef = nullptr;

JNIEXPORT void JNICALL Java_com_example_MainActivity_init(JNIEnv* env, jobject thiz) {
    if (globalRef != nullptr) {
        env->DeleteGlobalRef(globalRef);  // Clean up old ref
    }
    jobject localRef = ...;
    globalRef = env->NewGlobalRef(localRef);
}

JNIEXPORT void JNICALL Java_com_example_MainActivity_cleanup(JNIEnv* env, jobject thiz) {
    if (globalRef != nullptr) {
        env->DeleteGlobalRef(globalRef);
        globalRef = nullptr;
    }
}
```

### Pattern 3: Buffer Overflow

**Symptoms:**
```
Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR)
Crash at address shortly after valid buffer
```

**Cause:** Writing past buffer bounds

**Example (bad code):**
```cpp
JNIEXPORT void JNICALL Java_com_example_MainActivity_process(JNIEnv* env, jobject thiz, jbyteArray data) {
    jsize len = env->GetArrayLength(data);
    char buffer[100];
    env->GetByteArrayRegion(data, 0, len, (jbyte*)buffer);  // Overflow if len > 100!
}
```

**Fix:**
```cpp
JNIEXPORT void JNICALL Java_com_example_MainActivity_process(JNIEnv* env, jobject thiz, jbyteArray data) {
    jsize len = env->GetArrayLength(data);
    if (len > 100) {
        // Handle error or allocate dynamically
        return;
    }
    char buffer[100];
    env->GetByteArrayRegion(data, 0, len, (jbyte*)buffer);
}
```

### Pattern 4: Use-After-Free

**Symptoms:**
```
Fatal signal 11 (SIGSEGV), fault addr 0x12345678
Crash when accessing freed memory
```

**Cause:** Using memory after `free()` or `delete`

**Example (bad code):**
```cpp
char* buffer = (char*)malloc(100);
strcpy(buffer, "data");
free(buffer);
// Later...
strcpy(buffer, "more data");  // Crash!
```

**Fix:**
```cpp
char* buffer = (char*)malloc(100);
strcpy(buffer, "data");
free(buffer);
buffer = nullptr;  // Set to null after free

// Later...
if (buffer != nullptr) {
    strcpy(buffer, "more data");
}
```

### Pattern 5: Stack Overflow

**Symptoms:**
```
Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR)
Crash with very deep recursion
```

**Cause:** Infinite recursion or too deep recursion

**Example (bad code):**
```cpp
int factorial(int n) {
    return n * factorial(n - 1);  // No base case!
}
```

**Fix:**
```cpp
int factorial(int n) {
    if (n <= 1) return 1;  // Base case
    return n * factorial(n - 1);
}

// Or better: use iteration
int factorial_iterative(int n) {
    int result = 1;
    for (int i = 2; i <= n; i++) {
        result *= i;
    }
    return result;
}
```

### Pattern 6: Thread Safety Issue

**Symptoms:**
```
Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR)
Crash in multi-threaded code, hard to reproduce
```

**Cause:** Race condition, data race

**Example (bad code):**
```cpp
static int counter = 0;

void increment() {
    counter++;  // Not atomic! Race condition.
}

JNIEXPORT void JNICALL Java_com_example_MainActivity_nativeThread(JNIEnv* env, jobject thiz) {
    for (int i = 0; i < 1000; i++) {
        std::thread(increment).detach();
    }
    // Crash here when counter is corrupted
}
```

**Fix:**
```cpp
#include <mutex>
static int counter = 0;
static std::mutex counter_mutex;

void increment() {
    std::lock_guard<std::mutex> lock(counter_mutex);
    counter++;
}
```

### Pattern 7: Div by Zero

**Symptoms:**
```
Fatal signal 8 (SIGFPE), code 1 (FPE_INTDIV)
```

**Cause:** Integer division by zero

**Example (bad code):**
```cpp
int divide(int a, int b) {
    return a / b;  // Crash if b == 0
}
```

**Fix:**
```cpp
int divide(int a, int b) {
    if (b == 0) {
        return 0;  // Or handle error
    }
    return a / b;
}
```

## Debugging Tools

### Address Sanitizer (ASan)

**Enable in gradle:**
```gradle
android {
    defaultConfig {
        externalNativeBuild {
            cmake {
                arguments "-DANDROID_ARM_MODE=arm", "-DANDROID_STL=c++_shared"
                cFlags "-fsanitize=address -fno-omit-frame-pointer"
                ldFlags "-fsanitize=address"
            }
        }
    }
}
```

ASan detects:
- Use-after-free
- Heap buffer overflow
- Stack buffer overflow
- Memory leaks

### GDB Attached Debugging

```bash
# Start app with debuggable library
adb push app/build/outputs/apk/debug/app-debug.apk /data/local/tmp/
adb shell pm install /data/local/tmp/app-debug.apk

# Find PID
adb shell pidof com.example.app

# Attach gdb
adb shell gdbserver :5039 --attach $(pidof com.example.app)
adb forward tcp:5039 tcp:5039

# On host:
$ANDROID_NDK/prebuilt/linux-x86_64/bin/gdb
(gdb) target remote :5039
(gdb) continue
```

### Breakpad Crash Reporting

**Setup in CMakeLists.txt:**
```cmake
find_package(breakpad_client REQUIRED)

target_link_libraries(your_lib
    breakpad_client
)
```

**Initialize in JNI:**
```cpp
#include "client/linux/handler/exception_handler.h"

bool DumpCallback(const google_breakpad::MinidumpDescriptor& descriptor,
                  void* context,
                  bool succeeded) {
    // Upload minidump to crash server
    return succeeded;
}

void InitBreakpad() {
    google_breakpad::MinidumpDescriptor descriptor("/data/local/tmp");
    new google_breakpad::ExceptionHandler(descriptor, NULL, DumpCallback, NULL, true, -1);
}
```

## Prevention Best Practices

### 1. Null Checks

```cpp
// Always check pointers before dereferencing
if (ptr == nullptr) {
    // Handle error
}
```

### 2. JNI Exception Checking

```cpp
jobject obj = env->NewObject(clazz, mid);
if (env->ExceptionCheck()) {
    env->ExceptionDescribe();
    env->ExceptionClear();
    return;
}
```

### 3. Buffer Bounds Checking

```cpp
// Always verify buffer sizes
if (input_len > buffer_size) {
    // Handle error or truncate
}
```

### 4. Use Smart Pointers (C++)

```cpp
#include <memory>
std::unique_ptr<MyClass> ptr(new MyClass());
// Automatically deleted when out of scope
```

### 5. Enable Compiler Warnings

```cmake
target_compile_options(your_lib PRIVATE
    -Wall
    -Wextra
    -Werror
    -Wno-unused-parameter
)
```

### 6. Unit Testing Native Code

```cpp
#include <gtest/gtest.h>

TEST(NativeTest, NullPointerHandling) {
    EXPECT_EQ(handle_null_pointer(nullptr), ERROR_CODE);
}

TEST(NativeTest, BufferOverflow) {
    char buffer[100];
    EXPECT_EQ(process_data(buffer, 101), ERROR_BUFFER_TOO_SMALL);
}
```

## Advanced: Register Analysis

From crash dump, register values reveal crash context:

```
x0  0000000000000000  x1  0000000000000001
x2  0000000000000002  x3  0000000000000003
```

**ARM64 calling convention:**
- `x0` - `x7`: Arguments/return value
- `x0`: First argument or return value
- `x29`: Frame pointer
- `x30`: Link register (return address)

**Interpretation:**
```
x0 = 0x0000000000000000  # Likely "this" pointer or first arg is null
```

This suggests calling a method on a null object.

## Cross-Referencing with Java

When native crash is called from Java:

```
#02 pc 00345678  /system/lib64/libart.so (art_quick_generic_jni_trampoline+...)
#03 pc 000abcde  /system/lib64/libart.so (art_quick_invoke_stub+...)
```

1. Find the Java method calling native:
```bash
adb logcat -d | grep -B 20 "FATAL SIGNAL" | grep "java."
```

2. Check Java stack trace for context

3. Verify JNI method signature matches

## Resources

- [NDK Stack Documentation](https://developer.android.com/ndk/guides/ndk-stack)
- [Tombstone Format](https://source.android.com/devices/tech/debug/native-crash)
- [JNI Best Practices](https://developer.android.com/training/articles/perf-jni)
