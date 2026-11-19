"""Download World Bank indicators and cache them locally.

Uses the public World Bank Indicators API (v2), which needs no API key:
https://datahelpdesk.worldbank.org/knowledgebase/articles/889392

The first run downloads the data and saves it as a CSV. Later runs read the CSV,
so the analysis is reproducible and works offline. Pass ``refresh=True`` to
download the latest figures again.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

API = "https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}"


def _get_json(url: str, retries: int = 3) -> list:
    request = Request(url, headers={"User-Agent": "africa-economic-trends/1.0"})
    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except OSError:
            if attempt == retries:
                raise
            time.sleep(2 * attempt)
    return []


def fetch_indicator(indicator: str, countries: list[str], start: int, end: int) -> pd.DataFrame:
    """Return one indicator for the given ISO3 country codes in long format."""
    url = (
        API.format(countries=";".join(countries), indicator=indicator)
        + f"?format=json&date={start}:{end}&per_page=20000"
    )
    payload = _get_json(url)
    if len(payload) < 2 or payload[1] is None:
        raise ValueError(f"No data returned for {indicator}: {payload[0] if payload else 'empty response'}")
    return pd.DataFrame(
        {
            "country_code": row["countryiso3code"],
            "country": row["country"]["value"],
            "indicator_code": indicator,
            "indicator": row["indicator"]["value"],
            "year": int(row["date"]),
            "value": row["value"],
        }
        for row in payload[1]
    )


def load_indicators(
    indicators: dict[str, str],
    countries: list[str],
    start: int,
    end: int,
    cache: Path,
    refresh: bool = False,
) -> pd.DataFrame:
    """Load indicators from the cache, downloading them first if needed.

    ``indicators`` maps World Bank indicator codes to short column names.
    Returns long-format data with a ``series`` column holding the short name.
    """
    cache = Path(cache)
    if cache.exists() and not refresh:
        data = pd.read_csv(cache)
    else:
        frames = [fetch_indicator(code, countries, start, end) for code in indicators]
        data = pd.concat(frames, ignore_index=True)
        cache.parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(cache, index=False)
    data["series"] = data["indicator_code"].map(indicators)
    return data.sort_values(["series", "country_code", "year"]).reset_index(drop=True)
