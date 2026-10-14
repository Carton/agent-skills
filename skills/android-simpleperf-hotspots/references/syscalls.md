# Syscall and IPC Follow-up

Use this only when the sampled hot stack suggests polling, IPC, synchronization,
or opaque kernel work. Strace is optional and may require privileges unavailable
on a production device. It does not replace CPU sampling or scheduling evidence.

Select the exact hot TID and confirm it still belongs to the expected PID through
`/proc/PID/task/TID/comm` and `status`. Verify the device's strace path/options and
`timeout` availability. Run after the baseline measurement: ptrace perturbs
scheduling, syscall latency, and throughput.

Start with a short summary, choosing the syscall set from the sampled path:

```sh
"$ADB" shell timeout 3 "$DEVICE_STRACE" -c \
  -e trace=read,write,writev,poll,ppoll,epoll_wait,futex,ioctl \
  -p "$HOT_TID" -o /data/local/tmp/strace-UNIQUE-summary.txt
```

Then use a narrow detailed trace if counts do not explain the loop:

```sh
"$ADB" shell timeout 5 "$DEVICE_STRACE" -ttt -T -yy -s 256 \
  -e trace=read,write,writev,poll,ppoll,epoll_wait,futex,ioctl \
  -p "$HOT_TID" -o /data/local/tmp/strace-UNIQUE-detail.txt
```

Pull both outputs into the evidence directory. A timeout exit can be expected;
inspect attachment errors and trace completeness before interpreting the file.
Avoid process-wide `-f` unless already-selected threads cannot explain the path.
Increase string length or attach a known peer only when framing/order requires it.

- Calculate call rates from the actual trace window; inspect immediate-return
  loops, repeated errors, and periodic request/reply patterns.
- Match `-yy` pipe/socket inode or fd paths to distinguish file I/O and IPC peers.
- `-T` includes blocked elapsed syscall time and tracing overhead; it is not CPU
  execution time. Summary `-c` normally accounts system CPU time (`-w` selects wall
  time on supporting versions); its percentages are not application CPU utilization.
- Absolute `-ttt` timestamps are epoch time; map them to the simpleperf clock before
  correlating. Sequential captures support rate/path comparisons, not exact event
  matching.
- Reads/writes need not map one-to-one to messages. Reconstruct each direction as
  a byte stream before decoding framing; use the protocol from the exact build.

State what CPU samples demonstrate separately from what syscall traces suggest.
For blocker/waker chains, runnable delay, or GPU waits, collect scheduling/frame
evidence instead of treating syscall duration as the full cause of latency.

Reference: [strace manual](https://man7.org/linux/man-pages/man1/strace.1.html).
