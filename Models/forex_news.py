import cloudscraper
from bs4 import BeautifulSoup
import pandas as pd
import time

scraper = cloudscraper.create_scraper()

def scrape_week(week):
    url = f"https://www.forexfactory.com/calendar?week={week}"
    print(f"Scraping {url}")

    res = scraper.get(url)
    soup = BeautifulSoup(res.text, "html.parser")

    rows = soup.select("tr.calendar__row")

    data = []

    current_date = None

    for row in rows:
        # Extract date (only appears sometimes)
        date_cell = row.select_one("td.calendar__date")
        if date_cell and date_cell.text.strip():
            current_date = date_cell.text.strip()

        # Extract time
        time_cell = row.select_one("td.calendar__time")
        time_val = time_cell.text.strip() if time_cell else ""

        # Extract currency
        currency_cell = row.select_one("td.calendar__currency")
        currency = currency_cell.text.strip() if currency_cell else ""

        # Extract impact (FIXED)
        impact_cell = row.select_one("td.calendar__impact span")
        impact = impact_cell["title"].strip() if impact_cell and impact_cell.has_attr("title") else None

        # Extract event
        event_cell = row.select_one("td.calendar__event")
        event = event_cell.text.strip() if event_cell else ""

        # Actual
        event_cell = row.select_one("td.calendar__actual")
        event = event_cell.text.strip() if event_cell else ""

        # Forcast
        event_cell = row.select_one("td.calendar__forcast")
        event = event_cell.text.strip() if event_cell else ""

        # Previous
        event_cell = row.select_one("td.calendar__previous")
        event = event_cell.text.strip() if event_cell else ""

        # Skip empty rows
        if not current_date or not currency or not event:
            continue

        data.append({
            "Date": current_date,
            "Time": time_val,
            "Currency": currency,
            "Impact": impact,
            "Event": event,
            "Actual": actual,
            "Forecast": forecast,
            "Previous": previous
        })

    df = pd.DataFrame(data)

    if df.empty:
        return df

    # =========================
    # 🔧 DATA CLEANING SECTION
    # =========================

    # Add year from week string
    year = week.split('.')[-1]
    df["Date"] = df["Date"] + f" {year}"

    # Fix time
    df["Time"] = df["Time"].replace("", "12:00am")

    # Remove "All Day" and invalid entries
    df = df[~df["Time"].str.contains("All Day", na=False)]
    df = df[~df["Time"].str.contains("Tentative", na=False)]

    # Create datetime
    df["Datetime"] = pd.to_datetime(
        df["Date"] + " " + df["Time"],
        format="%a %b %d %Y %I:%M%p",
        errors="coerce"
    )

    # Drop broken rows
    df = df.dropna(subset=["Datetime"])

    # Fix impact NaN → label properly
    df["Impact"] = df["Impact"].fillna("Low")

    # Optional: filter only USD & JPY (you can remove this if needed)
    df = df[df["Currency"].isin(["USD", "JPY"])]

    # Sort
    df = df.sort_values("Datetime").reset_index(drop=True)

    return df


def scrape_range(start_year=2006, end_year=2026):
    all_data = []

    for year in range(start_year, end_year + 1):
        for month in [
            "jan", "feb", "mar", "apr", "may", "jun",
            "jul", "aug", "sep", "oct", "nov", "dec"
        ]:
            for day in [1, 8, 15, 22]:
                week = f"{month}{day}.{year}"

                try:
                    df = scrape_week(week)

                    if not df.empty:
                        all_data.append(df)

                    time.sleep(1)  # avoid blocking

                except Exception as e:
                    print(f"Error on {week}: {e}")
                    continue

    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)

        # Remove duplicates (important)
        final_df = final_df.drop_duplicates()

        return final_df

    return pd.DataFrame()


# =========================
# 🚀 RUN SCRAPER
# =========================

df = scrape_range(2024, 2024)

print("Total rows:", len(df))
print(df.head())

# Save
df.to_csv("forex_news_clean.csv", index=False)