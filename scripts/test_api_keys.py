"""Utility script to sanity-check external API credentials.

Each test performs a lightweight, non-destructive request against the
provider and reports whether authentication succeeded. Results are printed
to stdout so you can review successes or actionable failure messages.

Usage::

    python scripts/test_api_keys.py

Notes:
- These checks consume API quota; run sparingly in production.
- Network errors or provider-side rate limits will be reported as failures.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    genai = None

try:
    from configs import api_keys
except ImportError as exc:  # pragma: no cover - configuration issue
    sys.stderr.write(f"[FATAL] Unable to import configs.api_keys: {exc}\n")
    sys.exit(1)


TIMEOUT = 30  # seconds


@dataclass
class TestResult:
    name: str
    success: bool
    message: str
    extra: Optional[Dict[str, object]] = None


def _format_result(result: TestResult) -> str:
    status = "PASS" if result.success else "FAIL"
    message = result.message if result.message else ""
    details = ""
    if result.extra:
        try:
            payload = json.dumps(result.extra, indent=2, default=str)
        except TypeError:
            payload = str(result.extra)
        details = f"\n    Details: {payload}"
    return f"[{status}] {result.name}: {message}{details}"


def _summarize_http_error(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        try:
            body = exc.response.text
            snippet = body[:200].strip()
        except Exception:
            snippet = "<unable to read response body>"
        return f"HTTP {status}: {snippet}"
    return str(exc)


def test_clay() -> TestResult:
    """Verify the Clay API key by performing a sample enrichment lookup."""
    url = "https://api.clay.com/v1/enrichment/company"
    headers = {
        "Authorization": f"Bearer {api_keys.CLAY_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"domain": "google.com"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        company = data.get("company", {})
        name = company.get("name") or company.get("legal_name") or "company"
        return TestResult("Clay", True, f"Company lookup succeeded for {name}")
    except Exception as exc:  # pragma: no cover - network dependency
        return TestResult("Clay", False, _summarize_http_error(exc))


def test_apollo() -> TestResult:
    """Perform a minimal Apollo health check using the API key."""
    url = "https://api.apollo.io/v1/auth/health"
    headers = {"X-Api-Key": api_keys.APOLLO_API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if data.get("healthy") and data.get("is_logged_in"):
            return TestResult("Apollo", True, "API key authenticated")
        return TestResult("Apollo", False, f"Unexpected response: {data}")
    except Exception as exc:  # pragma: no cover - network dependency
        return TestResult("Apollo", False, _summarize_http_error(exc))


def test_pdl() -> TestResult:
    """Hit People Data Labs company lookup with a public domain."""
    url = "https://api.peopledatalabs.com/v5/company/enrich"
    params = {"website": "google.com"}
    headers = {"X-API-Key": api_keys.PDL_API_KEY}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        name = data.get("name") or data.get("organization") or "company"
        return TestResult("PeopleDataLabs", True, f"Lookup succeeded for {name}")
    except Exception as exc:  # pragma: no cover - network dependency
        return TestResult("PeopleDataLabs", False, _summarize_http_error(exc))


def test_sendgrid() -> TestResult:
    """Fetch the SendGrid account profile to validate the API key."""
    url = "https://api.sendgrid.com/v3/user/account"
    headers = {
        "Authorization": f"Bearer {api_keys.SENDGRID_API_KEY}",
        "Accept": "application/json",
    }
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        username = data.get("username") or data.get("email") or "account"
        return TestResult("SendGrid", True, f"Authenticated as {username}")
    except Exception as exc:  # pragma: no cover - network dependency
        return TestResult("SendGrid", False, str(exc))


def test_gemini() -> TestResult:
    """Run a tiny generation request against Gemini."""
    if genai is None:
        return TestResult("Gemini", False, "google-generativeai package is not installed")

    try:
        genai.configure(api_key=api_keys.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = "State the current year as a number only."
        start = time.time()
        result = model.generate_content(prompt)
        latency_ms = round((time.time() - start) * 1000, 1)
        text = result.text.strip() if result and result.text else "(empty response)"
        return TestResult("Gemini", True, f"Response: {text}", {"latency_ms": latency_ms})
    except Exception as exc:  # pragma: no cover - network dependency
        return TestResult("Gemini", False, str(exc))


def main() -> int:
    tests: Dict[str, Callable[[], TestResult]] = {
        "clay": test_clay,
        "apollo": test_apollo,
        "pdl": test_pdl,
        "sendgrid": test_sendgrid,
        "gemini": test_gemini,
    }

    passed = 0
    total = len(tests)
    print("Running API credential checks...\n")
    for name, func in tests.items():
        result = func()
        print(_format_result(result))
        if result.success:
            passed += 1

    summary = f"\nSummary: {passed}/{total} checks passed."
    print(summary)
    return 0 if passed == total else 1


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())

