
import json
import time
import random
import argparse
import csv
from datetime import datetime

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

WEEKLY_JSON_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def fetch_this_week_json(max_retries=5, base_delay=5.0):
    """
    Fetch the current week's calendar via the official JSON export.
    Retries with exponential backoff on 429 (Too Many Requests).
    """
    last_error = None
    for attempt in range(max_retries):
        resp = requests.get(WEEKLY_JSON_URL, headers=HEADERS, timeout=15)

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else base_delay * (2 ** attempt)
            wait += random.uniform(0, 1.5)  # jitter
            print(f"429 rate limited, waiting {wait:.1f}s before retry "
                  f"({attempt + 1}/{max_retries})...")
            time.sleep(wait)
            last_error = requests.exceptions.HTTPError(
                f"429 Too Many Requests for url: {WEEKLY_JSON_URL}"
            )
            continue

        resp.raise_for_status()
        return resp.json()

    raise last_error or RuntimeError("Failed to fetch calendar JSON after retries.")


def weeks_in_year(year):
    """
    Generate Forex Factory week codes (e.g. 'jan7.2024') for every week
    of the given year. Forex Factory weeks start on Monday, and the code
    is the lowercase month abbreviation + day + year of that Monday.
    """
    from datetime import date, timedelta

    d = date(year, 1, 1)
    # Walk back to the Monday on/before Jan 1
    d -= timedelta(days=d.weekday())

    codes = []
    while d.year <= year:
        if d.year == year or (d + timedelta(days=6)).year == year:
            codes.append(d.strftime("%b%d.%Y").lower())
        d += timedelta(days=7)
        if d.year > year:
            break

    return codes


def scrape_year_html(year, delay=4.0):
    """
    Scrape every week of a given year by looping over week codes.
    This makes ~52 requests, so it's slow by design (delay applies
    between every request) and can still get you rate-limited or
    Cloudflare-blocked if run too often.
    """
    codes = weeks_in_year(year)
    all_events = []

    for i, code in enumerate(codes, 1):
        print(f"[{i}/{len(codes)}] Fetching week {code}...")
        try:
            events = scrape_week_html(week_code=code, delay=delay)
            all_events.extend(events)
        except Exception as e:
            print(f"  Failed on week {code}: {e}")
            print("  Waiting longer before continuing...")
            time.sleep(delay * 3)

    return all_events


def scrape_week_html(week_code=None, delay=3.0):
    """
    Scrape a calendar page from HTML.

    week_code: e.g. "jan7.2024" for a specific week, or None for
               the current week. Forex Factory URLs look like:
               https://www.forexfactory.com/calendar?week=jan7.2024
    delay:     seconds to sleep before the request (be polite).
    """
    time.sleep(delay + random.uniform(0, 1.5))

    url = "https://www.forexfactory.com/calendar"
    params = {"week": week_code} if week_code else {}

    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()

    if "verification" in resp.text.lower() and "cloudflare" in resp.text.lower():
        raise RuntimeError(
            "Got a Cloudflare verification page instead of calendar data. "
            "Slow down your request rate or use the JSON export / a paid API instead."
        )

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("tr.calendar__row")

    events = []
    current_date = None
    for row in rows:
        date_cell = row.select_one(".calendar__date")
        if date_cell and date_cell.get_text(strip=True):
            current_date = date_cell.get_text(strip=True)

        time_cell = row.select_one(".calendar__time")
        currency_cell = row.select_one(".calendar__currency")
        impact_cell = row.select_one(".calendar__impact span")
        event_cell = row.select_one(".calendar__event")
        actual_cell = row.select_one(".calendar__actual")
        forecast_cell = row.select_one(".calendar__forecast")
        previous_cell = row.select_one(".calendar__previous")

        if not event_cell:
            continue

        events.append({
            "date": current_date,
            "time": time_cell.get_text(strip=True) if time_cell else None,
            "currency": currency_cell.get_text(strip=True) if currency_cell else None,
            "impact": impact_cell.get("title") if impact_cell else None,
            "event": event_cell.get_text(strip=True),
            "actual": actual_cell.get_text(strip=True) if actual_cell else None,
            "forecast": forecast_cell.get_text(strip=True) if forecast_cell else None,
            "previous": previous_cell.get_text(strip=True) if previous_cell else None,
        })

    return events


def save_csv(events, path):
    if not events:
        print("No events to save.")
        return
    keys = events[0].keys()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(events)
    print(f"Saved {len(events)} events to {path}")


def main():
    parser = argparse.ArgumentParser(description="Scrape Forex Factory calendar/news data")
    parser.add_argument(
        "--mode", choices=["json", "html"], default="html",
        help="json = current week via official export (recommended, current week only); "
             "html = scrape a calendar page (needed for other weeks/years) [default]"
    )
    parser.add_argument("--week", default=None, help="Single week code for html mode, e.g. jan7.2024")
    parser.add_argument("--year", type=int, default=2024,
                         help="Scrape an entire year in html mode, e.g. --year 2024 "
                              "(loops through all ~52 weeks; slow and rate-limit-prone by design) [default: 2024]")
    parser.add_argument("--delay", type=float, default=4.0,
                         help="Seconds to wait between requests in html mode (default 4.0)")
    parser.add_argument("--out", default="forex_factory_2024_events.csv", help="Output CSV path")
    args = parser.parse_args()

    if args.mode == "html" and args.year:
        events = scrape_year_html(args.year, delay=args.delay)
        save_csv(events, args.out)
        return

    if args.mode == "json":
        data = fetch_this_week_json()
        # Normalize field names slightly for consistency with html mode
        events = [{
            "date": e.get("date"),
            "time": e.get("date"),  # JSON export embeds full datetime in 'date'
            "currency": e.get("country"),
            "impact": e.get("impact"),
            "event": e.get("title"),
            "actual": e.get("actual"),
            "forecast": e.get("forecast"),
            "previous": e.get("previous"),
        } for e in data]
    else:
        events = scrape_week_html(week_code=args.week, delay=args.delay)

    save_csv(events, args.out)


if __name__ == "__main__":
    main()