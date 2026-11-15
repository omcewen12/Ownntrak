"""Thin, polite client for the Companies House public data API.

Authentication uses the REST API key as the HTTP basic auth username with a
blank password, as described in the Companies House developer documentation.
The key is never logged and never written to disk by this module.
"""
from __future__ import annotations

import time
from typing import Optional

import requests

BASE_URL = "https://api.company-information.service.gov.uk"
USER_AGENT = "ubo-ownership-mapper/1.0 (portfolio project)"


class CompaniesHouseError(Exception):
    """Raised for any API problem the caller should know about."""


class CompanyNotFound(CompaniesHouseError):
    """Raised when the company number the user asked for does not exist."""


def normalise_company_number(raw: str) -> str:
    """Tidy a user supplied company number.

    Companies House numbers are eight characters. Purely numeric numbers that
    lost their leading zeros are padded back to eight digits.
    """
    number = (raw or "").strip().upper().replace(" ", "")
    if number.isdigit() and len(number) < 8:
        number = number.zfill(8)
    return number


class CompaniesHouseClient:
    def __init__(
        self,
        api_key: str,
        *,
        session=None,
        timeout: float = 15.0,
        max_retries: int = 4,
        backoff: float = 2.0,
        sleep=time.sleep,
    ):
        if not api_key or not api_key.strip():
            raise ValueError("A Companies House REST API key is required.")
        self._auth = (api_key.strip(), "")
        self._session = session or requests.Session()
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff = backoff
        self._sleep = sleep
        self._cache: dict = {}
        self.calls = 0  # number of real HTTP requests made, useful for rate limit awareness

    # ------------------------------------------------------------------ core
    def _get(self, path: str, params: Optional[dict] = None):
        cache_key = (path, tuple(sorted((params or {}).items())))
        if cache_key in self._cache:
            return self._cache[cache_key]

        url = f"{BASE_URL}{path}"
        last_status = None
        for attempt in range(self._max_retries + 1):
            self.calls += 1
            response = self._session.get(
                url,
                params=params,
                auth=self._auth,
                timeout=self._timeout,
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            )
            status = response.status_code
            last_status = status

            if status == 200:
                data = response.json()
                self._cache[cache_key] = data
                return data
            if status == 404:
                self._cache[cache_key] = None
                return None
            if status in (401, 403):
                raise CompaniesHouseError(
                    "Companies House rejected the API key. Check that it is a REST key "
                    "created under a live application and that it was copied in full."
                )
            if status == 429 or status >= 500:
                wait = self._retry_delay(response, attempt)
                if attempt < self._max_retries:
                    self._sleep(wait)
                    continue
            else:
                raise CompaniesHouseError(f"Unexpected response {status} from {path}")

        raise CompaniesHouseError(
            f"Companies House kept returning {last_status} for {path}. "
            "The rate limit is 600 requests per five minutes, so wait a little and retry."
        )

    def _retry_delay(self, response, attempt: int) -> float:
        header = None
        try:
            header = response.headers.get("Retry-After")
        except Exception:  # pragma: no cover - defensive for odd fakes
            header = None
        if header:
            try:
                return max(float(header), 0.0)
            except ValueError:
                pass
        return self._backoff * (2 ** attempt)

    # ------------------------------------------------------------- endpoints
    def get_company(self, number: str) -> Optional[dict]:
        return self._get(f"/company/{number}")

    def get_pscs(self, number: str) -> list:
        """All persons with significant control, active and ceased, across pages."""
        items: list = []
        start = 0
        while True:
            data = self._get(
                f"/company/{number}/persons-with-significant-control",
                {"items_per_page": 100, "start_index": start},
            )
            if not data:
                break
            page = data.get("items", [])
            items.extend(page)
            start += len(page)
            if not page or start >= data.get("total_results", 0):
                break
        return items

    def get_psc_statements(self, number: str) -> list:
        data = self._get(f"/company/{number}/persons-with-significant-control-statements")
        return (data or {}).get("items", [])

    def get_exemptions(self, number: str) -> dict:
        data = self._get(f"/company/{number}/exemptions")
        return (data or {}).get("exemptions", {})
