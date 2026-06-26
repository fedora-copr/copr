import json
import logging
import os
import re
import threading
import time

log = logging.getLogger("__main__")

SAMPLE_INTERVAL_SEC = 10
GiB = 1024 ** 3


def _read_int(path):
    """Read a cgroup file containing a single integer."""
    try:
        with open(path) as f:
            text = f.read().strip()
            if text == "max":
                return 0
            return int(text)
    except (OSError, ValueError):
        return 0


def _read_stat_field(path, field):
    """Parse a 'key value' file (cpu.stat) and return the int for `field`."""
    try:
        with open(path) as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2 and parts[0] == field:
                    return int(parts[1])
    except (OSError, ValueError):
        pass

    return 0


def _read_io_total(path, field):
    """
    Parse io.stat (format: MAJ:MIN key=val key=val ...) and sum `field`
    across all devices.
    """
    total = 0
    try:
        with open(path) as f:
            for line in f:
                for token in line.split():
                    if token.startswith(field + "="):
                        total += int(token.split("=", 1)[1])
    except (OSError, ValueError):
        pass
    return total


def _read_psi_total(path):
    """
    Parse a PSI pressure file and return the cumulative 'total' from
    the 'some' line (microseconds).
    """
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("some "):
                    match = re.search(r"total=(\d+)", line)
                    if match:
                        return int(match.group(1))
    except (OSError, ValueError):
        pass
    return 0


class CgroupSampler:
    def __init__(self, cgroup_path, interval=SAMPLE_INTERVAL_SEC):
        self.cgroup_path = cgroup_path
        self.interval = interval
        self.samples = []
        self._prev_cpu_usec = None
        self._prev_t = None
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=5)

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self.samples.append(self._take_sample())
            except (OSError, ValueError):
                log.debug("Resource sampling tick failed", exc_info=True)

            self._stop_event.wait(self.interval)

    def _cg(self, filename):
        return os.path.join(self.cgroup_path, filename)

    def _take_sample(self):
        now = time.time()
        cpu_usage = _read_stat_field(self._cg("cpu.stat"), "usage_usec")

        cpu_pct = 0.0
        if self._prev_cpu_usec is not None and self._prev_t is not None:
            dt = now - self._prev_t
            if dt > 0:
                cpu_pct = (cpu_usage - self._prev_cpu_usec) / (dt * 1e6)

        self._prev_cpu_usec = cpu_usage
        self._prev_t = now

        return {
            "t": now,
            "rss_bytes": _read_int(self._cg("memory.current")),
            "swap_bytes": _read_int(self._cg("memory.swap.current")),
            "cpu_usage_usec": cpu_usage,
            "cpu_user_usec": _read_stat_field(
                self._cg("cpu.stat"), "user_usec"),
            "cpu_system_usec": _read_stat_field(
                self._cg("cpu.stat"), "system_usec"),
            "cpu_pct": round(cpu_pct, 4),
            "io_rbytes": _read_io_total(self._cg("io.stat"), "rbytes"),
            "io_wbytes": _read_io_total(self._cg("io.stat"), "wbytes"),
            "psi_cpu_total": _read_psi_total(self._cg("cpu.pressure")),
            "psi_mem_total": _read_psi_total(self._cg("memory.pressure")),
            "psi_io_total": _read_psi_total(self._cg("io.pressure")),
            "pids": _read_int(self._cg("pids.current")),
        }

    def compute_summary(self):
        if not self.samples:
            return {}

        rss_values = [s["rss_bytes"] for s in self.samples]

        # try reading it from kernel; if the cgroup was already
        # killed, fall back to sampled max
        memory_peak = _read_int(self._cg("memory.peak"))
        if memory_peak == 0:
            memory_peak = max(rss_values)

        swap_peak = _read_int(self._cg("memory.swap.peak"))
        if swap_peak == 0:
            swap_values = [s["swap_bytes"] for s in self.samples]
            swap_peak = max(swap_values)

        effective_peak = memory_peak if memory_peak > 0 else max(rss_values)

        sorted_rss = sorted(rss_values)
        p95_idx = min(int(len(sorted_rss) * 0.95), len(sorted_rss) - 1)

        high_threshold = effective_peak * 0.8
        high_count = sum(1 for v in rss_values if v > high_threshold)

        first = self.samples[0]
        last = self.samples[-1]

        cpu_user_delta = last["cpu_user_usec"] - first["cpu_user_usec"]
        cpu_system_delta = last["cpu_system_usec"] - first["cpu_system_usec"]

        io_read = last["io_rbytes"] - first["io_rbytes"]
        io_write = last["io_wbytes"] - first["io_wbytes"]

        cpu_pcts = [s["cpu_pct"] for s in self.samples]

        return {
            "peak_rss_gb": effective_peak / GiB,
            "peak_sampled_rss_gb": max(rss_values) / GiB,
            "swap_peak_gb": swap_peak / GiB,
            "mean_rss_gb": (sum(rss_values) / len(rss_values)) / GiB,
            "p95_rss_gb": sorted_rss[p95_idx] / GiB,
            "sustained_high_rss_pct": high_count / len(rss_values),
            "cpu_user_seconds": cpu_user_delta / 1e6,
            "cpu_system_seconds": cpu_system_delta / 1e6,
            "cpu_pct_mean": round(sum(cpu_pcts) / len(cpu_pcts), 4),
            "cpu_pct_max": max(cpu_pcts),
            "io_read_gb": max(io_read, 0) / GiB,
            "io_write_gb": max(io_write, 0) / GiB,
            "sample_count": len(self.samples),
            "sample_interval_seconds": self.interval,
        }


def write_resource_results(resultdir, sampler):
    try:
        summary = sampler.compute_summary()
        if summary:
            stats_path = os.path.join(resultdir, "resource_stats.json")
            with open(stats_path, "w") as f:
                json.dump(summary, f, indent=4)
            log.info("Resource stats written to %s", stats_path)
    except Exception:
        log.warning("Failed to write resource_stats.json", exc_info=True)

    try:
        if sampler.samples:
            samples_path = os.path.join(resultdir, "resource_samples.jsonl")
            with open(samples_path, "w") as f:
                for sample in sampler.samples:
                    f.write(json.dumps(sample) + "\n")
            log.info("Resource samples (%d) written to %s",
                     len(sampler.samples), samples_path)
    except Exception:
        log.warning("Failed to write resource_samples.jsonl", exc_info=True)
