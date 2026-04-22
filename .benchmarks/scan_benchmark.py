#!/usr/bin/env -S uv run python
"""Benchmark harness for skill scanner performance.

Usage:
    uv run python .benchmarks/scan_benchmark.py

Measures:
- scan_skills_dir() total time at scale (10, 50, 100, 500, 1000 skills)
- Per-operation breakdown: glob, YAML parsing, git integration
- fd vs iterdir() fallback comparison

E4 Threshold (trigger for Rust rewrite):
    Scanning >2s for any scale AND bottleneck confirmed in file/YAML processing
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Ensure skillr is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skillr.scanner import (
    _fast_skill_md_glob,
    _iterdir_skill_md_glob,
    get_git_commit_hash,
    is_git_repo,
    parse_skill_frontmatter,
    scan_skills_dir,
)


def _create_skill(skill_dir: Path, name: str, description: str = "Test skill description") -> None:
    """Create a minimal SKILL.md file."""
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        f"""---
name: {name}
description: {description}
---

# {name}

This is a test skill.
""",
        encoding="utf-8",
    )


def _create_benchmark_skills_dir(tmp_path: Path, count: int) -> Path:
    """Create a skills directory with `count` skill subdirectories."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    for i in range(count):
        skill_dir = skills_dir / f"skill-{i:04d}"
        skill_dir.mkdir()
        _create_skill(skill_dir, f"skill-{i:04d}", f"Test skill number {i}")
    return skills_dir


def _purge_fscache():
    """Drop filesystem caches (macOS)."""
    subprocess.run(["purge", "-q", "."], capture_output=True)


def benchmark_scan_total(skills_dir: Path, count: int) -> float:
    """Measure total time for scan_skills_dir()."""
    start = time.perf_counter()
    skills, file_mtimes = scan_skills_dir(skills_dir)
    elapsed = time.perf_counter() - start
    assert len(skills) == count, f"Expected {count} skills, got {len(skills)}"
    return elapsed


def benchmark_yaml_parse(skills_dir: Path, count: int) -> float:
    """Measure YAML parsing time for all skills."""
    start = time.perf_counter()
    for i in range(count):
        skill_md = skills_dir / f"skill-{i:04d}" / "SKILL.md"
        parse_skill_frontmatter(skill_md)
    elapsed = time.perf_counter() - start
    return elapsed


def benchmark_glob(skills_dir: Path, count: int) -> tuple[float, float, bool]:
    """Compare fd glob vs iterdir fallback. Returns (fd_time, iter_time, fd_used)."""
    # fd glob
    start = time.perf_counter()
    fd_paths = _fast_skill_md_glob(skills_dir)
    fd_time = time.perf_counter() - start

    # iterdir fallback
    start = time.perf_counter()
    _iterdir_skill_md_glob(skills_dir)
    iter_time = time.perf_counter() - start

    fd_used = fd_paths is not None
    return fd_time, iter_time, fd_used


def benchmark_git_is_repo(skills_dir: Path, count: int) -> float:
    """Measure is_git_repo() subprocess overhead (N calls)."""
    start = time.perf_counter()
    for _ in range(count):
        is_git_repo(skills_dir)
    elapsed = time.perf_counter() - start
    return elapsed


def benchmark_git_hash(skills_dir: Path, count: int) -> float:
    """Measure get_git_commit_hash() subprocess overhead (N calls)."""
    start = time.perf_counter()
    for _ in range(count):
        get_git_commit_hash(skills_dir)
    elapsed = time.perf_counter() - start
    return elapsed


def run():
    counts = [10, 50, 100, 500, 1000]

    print("=" * 80)
    print("Skillr Scanner Benchmark — Python Implementation")
    print("=" * 80)
    print()

    results: dict[int, dict] = {}

    for count in counts:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            skills_dir = _create_benchmark_skills_dir(tmp_path, count)

            # Warm filesystem cache
            _purge_fscache()
            scan_skills_dir(skills_dir)  # warmup

            # Run benchmarks
            total_time = benchmark_scan_total(skills_dir, count)
            fd_time, iter_time, fd_used = benchmark_glob(skills_dir, count)
            yaml_time = benchmark_yaml_parse(skills_dir, count)

            results[count] = {
                "total": total_time,
                "fd_time": fd_time,
                "iter_time": iter_time,
                "fd_used": fd_used,
                "yaml_time": yaml_time,
            }

    # Print results table
    print(
        f"{'Count':>6} | {'Total (ms)':>10} | {'Per-file (ms)':>12} | {'fd (ms)':>8} | {'iterdir (ms)':>12} | {'yaml (ms)':>9} | fd_used"
    )
    print("-" * 85)
    for count, r in results.items():
        per_file = r["total"] / count * 1000
        print(
            f"{count:>6} | {r['total'] * 1000:>10.1f} | {per_file:>12.2f} | "
            f"{r['fd_time'] * 1000:>8.2f} | {r['iter_time'] * 1000:>12.2f} | "
            f"{r['yaml_time'] * 1000:>9.1f} | {'YES' if r['fd_used'] else 'NO '}"
        )

    print()
    print("=" * 80)
    print("E4 Threshold Check")
    print("=" * 80)

    threshold_exceeded = False
    bottleneck_is_files_yaml = False

    for count, r in results.items():
        total = r["total"]
        glob_pct = r["fd_time"] / total * 100 if total > 0 else 0
        yaml_pct = r["yaml_time"] / total * 100 if total > 0 else 0

        exceeded = total > 2.0
        bottleneck = (r["fd_time"] / total > 0.3) or (r["yaml_time"] / total > 0.3)

        if exceeded:
            threshold_exceeded = True
        if bottleneck:
            bottleneck_is_files_yaml = True

        status = "🚫 EXCEEDS 2s" if exceeded else "✅ OK"
        print(
            f"  [{count:4d} skills] total={total * 1000:7.1f}ms  glob={glob_pct:5.1f}%  yaml={yaml_pct:5.1f}%  {status}"
        )

    print()
    e4_should_start = threshold_exceeded and bottleneck_is_files_yaml
    if e4_should_start:
        print("  ✅ E4 TRIGGER: Start Rust scanner rewrite")
    else:
        print("  ❌ E4 TRIGGER: Do NOT start Rust — Python performance is acceptable")

    print()
    print("Notes:")
    print("  - fd: subprocess wrapper around `fd` CLI tool (fast glob)")
    print("  - iterdir: pure-Python Path.iterdir() fallback when fd unavailable")
    print("  - yaml_time: pure-Python yaml.safe_load() per file")
    print("  - Threshold: >2s total scan time AND bottleneck in glob/yaml")
    print()


if __name__ == "__main__":
    run()
