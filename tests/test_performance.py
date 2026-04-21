"""Performance tests and profiling for Skillr.

These tests use pytest-benchmark for regression tracking and include
profiling guidance for identifying bottlenecks.

Run benchmarks:
    pytest tests/test_performance.py --benchmark-only

Profile with cProfile:
    python -m cProfile -s cumtime -m pytest tests/test_performance.py -v 2>&1 | head -50
"""

from __future__ import annotations

import json
import random
import string
from pathlib import Path

import pytest

from skillr.intent import build_intent_prompt, parse_intent_response
from skillr.matcher import build_matcher_prompt, keyword_filter, parse_matcher_response
from skillr.models import IntentSpec, SkillMeta

# === Benchmark fixtures ===


def generate_skills(count: int) -> list[SkillMeta]:
    """Generate N skills for benchmark testing."""
    skills = []
    for i in range(count):
        name = f"skill-{i}-{''.join(random.choices(string.ascii_lowercase, k=8))}"
        desc = f"Description for skill {i} with some keywords like api rest database auth"
        skills.append(
            SkillMeta(name=name, description=desc, file_path=Path(f"/skills/{i}/SKILL.md"))
        )
    return skills


@pytest.fixture
def skill_list_100():
    return generate_skills(100)


@pytest.fixture
def skill_list_1000():
    return generate_skills(1000)


@pytest.fixture
def skill_list_10000():
    return generate_skills(10000)


@pytest.fixture
def intent_spec():
    return IntentSpec(
        original_task="build a REST API with authentication",
        intent="Build a REST API with JWT authentication",
        constraints=["must use JWT"],
        keywords=["api", "rest", "jwt", "auth", "python"],
    )


@pytest.fixture
def intent_response_json():
    return json.dumps(
        {
            "intent": "Build a REST API with JWT authentication",
            "constraints": ["must use JWT", "python required"],
            "keywords": ["api", "rest", "jwt", "auth"],
        }
    )


@pytest.fixture
def matcher_response_json():
    return json.dumps(
        [
            {
                "name": f"skill-{i}",
                "score": round(random.uniform(0.5, 1.0), 2),
                "match_reason": f"Reason {i}",
            }
            for i in range(20)
        ]
    )


# === keyword_filter benchmarks ===


def test_keyword_filter_100(benchmark, skill_list_100):
    keywords = ["api", "rest", "auth"]
    result = benchmark(keyword_filter, skill_list_100, keywords)
    assert result is not None


def test_keyword_filter_1000(benchmark, skill_list_1000):
    keywords = ["api", "rest", "auth", "database"]
    result = benchmark(keyword_filter, skill_list_1000, keywords)
    assert result is not None


def test_keyword_filter_10000(benchmark, skill_list_10000):
    keywords = ["api", "rest", "auth", "database", "migration"]
    result = benchmark(keyword_filter, skill_list_10000, keywords)
    assert result is not None


# === parse_intent_response benchmarks ===


def test_parse_intent_response(benchmark, intent_response_json):
    result = benchmark(parse_intent_response, intent_response_json, "original task")
    assert result is not None


def test_parse_intent_response_large(benchmark):
    # Simulate larger LLM response with extra context
    large_response = (
        '{"intent": "Build a REST API with JWT authentication", "constraints": ["must use JWT"], "keywords": ["api", "rest", "jwt"]}'
        + " " * 100  # extra padding to simulate verbose LLM output
    )
    result = benchmark(parse_intent_response, large_response, "original task")
    assert result is not None


# === parse_matcher_response benchmarks ===


def test_parse_matcher_response(benchmark, matcher_response_json):
    result = benchmark(parse_matcher_response, matcher_response_json)
    assert result is not None


def test_parse_matcher_response_large(benchmark):
    # Large response with many skills
    large_response = json.dumps(
        [
            {
                "name": f"skill-{i}",
                "score": round(random.uniform(0.5, 1.0), 2),
                "match_reason": f"Match reason for skill {i}",
            }
            for i in range(100)
        ]
    )
    result = benchmark(parse_matcher_response, large_response)
    assert result is not None


# === build_matcher_prompt benchmarks ===


def test_build_matcher_prompt_50(benchmark, skill_list_100, intent_spec):
    result = benchmark(build_matcher_prompt, skill_list_100[:50], intent_spec)
    assert result is not None


def test_build_matcher_prompt_100(benchmark, skill_list_100, intent_spec):
    result = benchmark(build_matcher_prompt, skill_list_100, intent_spec)
    assert result is not None


def test_build_matcher_prompt_500(benchmark, skill_list_1000, intent_spec):
    # Only use first 500
    result = benchmark(build_matcher_prompt, skill_list_1000[:500], intent_spec)
    assert result is not None


# === build_intent_prompt benchmarks ===


def test_build_intent_prompt(benchmark):
    result = benchmark(
        build_intent_prompt,
        "I want to build a comprehensive REST API with authentication and database integration",
    )
    assert result is not None


# === Profiling recommendations ===

# Profiled areas and expected bottlenecks:
#
# 1. keyword_filter with large skill lists:
#    - O(n * m) where n = skills, m = keywords
#    - With 10k skills and 5 keywords, this is the dominant CPU cost
#    - Mitigation: ensure retrieval_window=50 limits the passed skill count
#
# 2. parse_matcher_response with large JSON:
#    - Regex [\s\S]*? is non-greedy but still scans the full response
#    - For very large LLM responses (>10KB), this could be slow
#    - Mitigation: non-greedy match prevents over-matching
#
# 3. get_source_tracking_value subprocess calls:
#    - Each skills_dir triggers a git subprocess call
#    - 10 skills_dirs = 10 subprocess invocations
#    - Mitigation: consider caching or parallelizing with ThreadPoolExecutor
#
# To profile with py-spy (if available):
#   pip install py-spy
#   py-spy top -- python -m pytest tests/test_performance.py -v
#
# To profile with cProfile:
#   python -m cProfile -s cumtime -m pytest tests/test_performance.py 2>&1 | head -40
#
# Expected results on modern hardware:
#   keyword_filter (10k skills): ~5-20ms
#   parse_matcher_response (100 items): ~1-5ms
#   build_matcher_prompt (500 skills): ~10-30ms
#
# If benchmarks regress significantly (>2x), investigate recent changes
# before merging.
