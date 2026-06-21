import os
import re
import json
import requests
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from collections import defaultdict

IST = ZoneInfo("Asia/Kolkata")
YEAR = datetime.now(IST).year
TS = int(datetime.now(IST).timestamp())
TODAY_IST = datetime.now(IST).strftime("%Y%m%d")

META_URL = (
    f"https://raw.githubusercontent.com/"
    f"text2027mail/"
    f"bms-movies-data/refs/heads/main/"
    f"data/{YEAR}.json"
    f"?ts={TS}"
)

SUMMARY_URL = (
    f"https://raw.githubusercontent.com/"
    f"unknownman2024/"
    f"yearlydata/refs/heads/main/"
    f"moviedata/{YEAR}.json"
    f"?ts={TS}"
)


MIN_GROSS = 100000
MIN_SHOWS = 20
FORCE_REBUILD = False
REBUILD_YEAR = 2026

for y in range(2023, YEAR + 1):

    os.makedirs(f"{y}/hindi", exist_ok=True)
os.makedirs("data/hindi", exist_ok=True)

FORCE_YEAR_MAP = {}

force_year_path = (
    "data/hindi/forceyear_merged.json"
)

if os.path.exists(force_year_path):

    try:

        with open(
            force_year_path,
            "r",
            encoding="utf-8"
        ) as f:

            for row in json.load(f):

                slug = row.get("s")

                fy = row.get("fy")

                if (
                    slug
                    and fy
                ):

                    FORCE_YEAR_MAP[
                        slug
                    ] = int(fy)

        print(
            "Force year entries:",
            len(FORCE_YEAR_MAP)
        )

    except Exception as e:

        print(
            "Failed loading forceyear:",
            e
        )

from decimal import Decimal, ROUND_HALF_UP

MANUAL_FIELDS = [
    "d1os",
    "d2os",
    "d3os",
    "d4os",
    "wos",
    "tos",
    "vd",
]


def round05(v):

    # keep small values untouched
    if v < 0.5:
        return round(v, 2)

    return float(
        (
            Decimal(str(v)) * 20
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP
        ) / Decimal("20")
    )

def file_hash(path):

    if not os.path.exists(path):
        return None

    with open(path, "rb") as f:

        return hashlib.md5(f.read()).hexdigest()


def canonical_movie_name(title):

    title = title.lower()

    title = re.sub(r"\([^)]*\)", "", title)

    title = title.replace("&", "and")

    title = re.sub(r"['`´]", "", title)

    title = re.sub(r"[^a-z0-9]+", " ", title)

    title = re.sub(r"\s+", " ", title)

    return title.strip()


def slugify(text):

    text = text.lower()

    text = re.sub(r"[^a-z0-9]+", "-", text)

    return text.strip("-")


def get_multiplier(occupancy, shows):

    oxs = occupancy * shows

    if oxs >= 300000:
        return 0.93

    elif oxs >= 100000:
        return 0.925

    elif oxs >= 50000:
        return 0.92

    elif oxs >= 25000:
        return 0.91

    else:
        return 0.90


def normalize_title(title):

    title = title.lower()

    title = re.sub(r"\([^)]*\)", "", title)

    title = re.sub(r"[^a-z0-9]+", "", title)

    return title


def parse_movie_key(key):

    """
    Example:

    War 2 [2D | Hindi]

    War 2 [IMAX 2D | Hindi]
    """

    m = re.match(r"^(.*?)\s*\[(.*?)\|\s*(.*?)\]$", key)

    if not m:
        return None

    movie = m.group(1).strip()

    language = m.group(3).strip()

    return (movie, language)


print("Loading metadata...")

session = requests.Session()

session.headers.update(
    {
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
)

meta_resp = session.get(META_URL, timeout=120)

meta_resp.raise_for_status()

meta_text = meta_resp.text

print("META SIZE:", len(meta_text))
print("META HASH:", hashlib.md5(meta_text.encode()).hexdigest())

metadata = {}
metadata_slug = {}

for line in meta_text.splitlines():

    line = line.strip()

    if not line:
        continue

    try:

        obj = json.loads(line)

    except Exception:
        continue

    title = (obj.get("t") or "").strip()

    if not title:
        continue

    metadata[normalize_title(title)] = obj

    metadata_slug[slugify(title)] = obj

print("Metadata loaded:", len(metadata))

print("Building movie buckets...")

movie_titles = {}
movies = defaultdict(
    lambda: defaultdict(lambda: {"gross": 0, "sold": 0, "shows": 0, "seats": 0})
)


print("Loading yearly data...")

summary_resp = session.get(SUMMARY_URL, timeout=300)

summary_resp.raise_for_status()

print("SUMMARY SIZE:", len(summary_resp.text))
print("SUMMARY HASH:", hashlib.md5(summary_resp.text.encode()).hexdigest())

data = summary_resp.json()
print("\n=== SOURCE INFO ===")

last_updated = (
    data.get("lastUpdated")
    or data.get("updated")
    or data.get("last_updated")
    or data.get("generated")
    or data.get("timestamp")
)
print("Last Updated:", last_updated)

LAST_UPDATED = datetime.now(IST).strftime(
    "%Y-%m-%d %H:%M IST"
)

if "movies" in data:
    print("Movie Count:", len(data["movies"]))

print("===================\n")


movie_section = data.get("movies", {})

print("Movies:", len(movie_section))

for movie_key, movie_data in movie_section.items():

    parsed = parse_movie_key(movie_key)

    if not parsed:
        continue

    movie_name, language = parsed

    if language.lower() != "hindi":
        continue

    daily = movie_data.get("daily", {})

    for date_key, row in daily.items():

        try:

            gross = float(row[0])

            sold = float(row[1])

            shows = float(row[2])

            occ = float(row[3])

        except Exception:

            continue

        seats = 0

        if occ > 0:

            seats = sold / (occ / 100)

        canonical_name = canonical_movie_name(movie_name)

        if canonical_name not in movie_titles:

            movie_titles[canonical_name] = movie_name

        bucket = movies[canonical_name][date_key]

        bucket["gross"] += gross
        bucket["sold"] += sold
        bucket["shows"] += shows
        bucket["seats"] += seats

print("Hindi movies found:", len(movies))

generated_files = set()
year_indexes = defaultdict(list)

print("Creating output...")

for canonical_name, days_data in movies.items():

    movie_name = movie_titles[canonical_name]

    valid_dates = []

    for date_key, day in days_data.items():

        merged_gross = day["gross"]

        merged_shows = day["shows"]

        if merged_gross < MIN_GROSS:
            continue

        if merged_shows < MIN_SHOWS:
            continue

        valid_dates.append(date_key)

    if not valid_dates:
        continue

    meta = metadata.get(normalize_title(canonical_name))

    if not meta:

        meta = metadata_slug.get(slugify(canonical_name))

    release_date = None

    if meta and meta.get("rd"):

        release_date = meta["rd"]

    else:

        earliest = min(valid_dates)

        release_date = datetime.strptime(earliest, "%Y%m%d").strftime("%Y-%m-%d")

    rd = datetime.strptime(release_date, "%Y-%m-%d")

    has_premieres = min(valid_dates) < rd.strftime("%Y%m%d")

    slug = slugify(canonical_name)
    
    release_year = FORCE_YEAR_MAP.get(
        slug,
        int(release_date[:4])
    )
    
    if slug in FORCE_YEAR_MAP:
    
        print(
            f"FORCED YEAR: {slug} -> {release_year}"
        )
    
    output = {
        "m": movie_name,
        "rd": release_date,
        "premiere": has_premieres,
        "v": 1,
        "src": "bfilmyapi",
    }

    if meta:

        for field in ["ec", "img", "og", "d", "g", "l", "rt", "ct"]:

            if field in meta:

                output[field] = meta[field]

    output_dir = f"{release_year}/hindi"

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"{slug}.json")

    existing_data = {}

    if os.path.exists(output_path):

        try:

            with open(output_path, "r", encoding="utf-8") as f:

                existing_data = json.load(f)

        except Exception:

            existing_data = {}

    manual_days = {}

    if existing_data.get("days"):

        for d in existing_data["days"]:

            day_no = d.get("d")

            if day_no is not None:

                manual_days[day_no] = d

    output["days"] = []
    total_nett = 0
    
    # latest source day irrespective of filters
    latest_date_key = max(days_data.keys())
    for date_key in sorted(valid_dates):

        day = days_data[date_key]

        gross = day["gross"]

        sold = day["sold"]

        shows = day["shows"]

        seats = day["seats"]

        occupancy = 0

        if seats > 0:

            occupancy = (sold / seats) * 100

        mf = get_multiplier(occupancy, shows)

        nett = round05((gross * mf) / 10000000)

        current_day = datetime.strptime(date_key, "%Y%m%d")

        if current_day < rd:

            day_no = 0

        else:

            day_no = (current_day - rd).days + 1

        is_latest_source_day = date_key == latest_date_key

        if day_no in manual_days and not is_latest_source_day:
            final_nett = manual_days[day_no].get("n", nett)
        else:
            final_nett = nett

        total_nett += final_nett

        output["days"].append({"d": day_no, "dt": int(date_key), "n": final_nett})

    output["days"].sort(key=lambda x: x["d"])

    if not output["days"]:
        continue

    output["tn"] = round05(total_nett)

    for field in MANUAL_FIELDS:

        if field in existing_data:

            output[field] = existing_data[field]

        else:

            output[field] = "" if field == "vd" else 0

    new_json = json.dumps(output, ensure_ascii=False, separators=(",", ":"))

    if os.path.exists(output_path):

        with open(output_path, "r", encoding="utf-8") as f:

            old_json = f.read()

        if (
            old_json == new_json
            and not (
                FORCE_REBUILD
                and release_year == REBUILD_YEAR
            )
        ):
        

            print("Unchanged:", slug)

            generated_files.add(os.path.abspath(output_path))

            max_day = 0

            for day in output["days"]:

                if day["d"] > max_day:

                    max_day = day["d"]

            year_indexes[release_year].append(
                {
                    "s": slug,
                    "n": output["tn"],
                    "d": max_day,
                    "d1os": output.get("d1os", 0),
                    "d2os": output.get("d2os", 0),
                    "d3os": output.get("d3os", 0),
                    "d4os": output.get("d4os", 0),
                    "wos": output.get("wos", 0),
                    "tos": output.get("tos", 0),
                    "vd": output.get("vd", ""),
                }
            )
            continue

    with open(output_path, "w", encoding="utf-8") as f:

        f.write(new_json)

    print("Saved:", output_path)

    generated_files.add(os.path.abspath(output_path))

    max_day = 0

    for day in output["days"]:

        if day["d"] > max_day:

            max_day = day["d"]

    year_indexes[release_year].append(
        {
            "s": slug,
            "n": output["tn"],
            "d": max_day,
            "d1os": output.get("d1os", 0),
            "d2os": output.get("d2os", 0),
            "d3os": output.get("d3os", 0),
            "d4os": output.get("d4os", 0),
            "wos": output.get("wos", 0),
            "tos": output.get("tos", 0),
            "vd": output.get("vd", ""),
        }
    )

print("\nCompleted.")

for idx_year, movies in year_indexes.items():

    movies.sort(key=lambda x: x["n"], reverse=True)

    index_path = f"data/hindi/{idx_year}.json"


    index_payload = {
        "last_updated": LAST_UPDATED,
        "movies": movies,
    }
    
    new_index_json = json.dumps(
        index_payload,
        ensure_ascii=False,
        separators=(",", ":")
    )

    write_index = True

    if os.path.exists(index_path):

        with open(index_path, "r", encoding="utf-8") as f:

            old_index_json = f.read()

        if old_index_json == new_index_json:

            write_index = False

            print("Index unchanged:", idx_year)

    if write_index:

        with open(index_path, "w", encoding="utf-8") as f:

            f.write(new_index_json)

        print("Updated:", index_path)

print("\nCompleted.")
