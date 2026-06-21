import os
import json
from collections import defaultdict

YEARS = [2023, 2024, 2025, 2026]
FORCE_YEAR = []

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            separators=(",", ":")
        )

slug_map = defaultdict(list)

for year in YEARS:

    folder = f"{year}/hindi"

    if not os.path.isdir(folder):
        continue

    for file in os.listdir(folder):

        if not file.endswith(".json"):
            continue

        slug = file[:-5]

        slug_map[slug].append(
            os.path.join(folder, file)
        )

for slug, paths in slug_map.items():

    if len(paths) <= 1:
        continue

    paths = sorted(paths)

    print(
        f"Merging {slug}"
    )

    files = []

    for path in paths:

        try:

            files.append(
                (
                    path,
                    load_json(path)
                )
            )

        except Exception as e:

            print(
                "Failed:",
                path,
                e
            )

    if len(files) <= 1:
        continue

    files.sort(
        key=lambda x:
        x[1].get(
            "rd",
            "9999-99-99"
        )
    )

    base_path, base = files[0]
    
    base_year = int(
        base_path.split("/")[0]
    )
    
    force_movie_name = (
        base.get("m")
        or slug.replace("-", " ").title()
    )

    merged_days = []

    earliest_rd = base.get(
        "rd"
    )

    best_meta = {}

    total_nett = 0
    total_gross = 0

    for path, data in files:

        rd = data.get("rd")

        if rd and (
            earliest_rd is None or
            rd < earliest_rd
        ):
            earliest_rd = rd

        for k, v in data.items():

            if (
                k == "days"
                or k == "tn"
                or k == "tg"
            ):
                continue

            if v not in (
                None,
                "",
                [],
                {}
            ):
                best_meta[k] = v

        for day in data.get(
            "days",
            []
        ):

            merged_days.append(
                day
            )

    # prefer dt when available,
    # otherwise use run day
    
    seen = {}
    
    for day in merged_days:
    
        if day.get("dt"):
    
            key = (
                "dt",
                day["dt"]
            )
    
        else:
    
            key = (
                "d",
                day.get("d", 0)
            )
    
        # prefer record containing dt
        if key not in seen:
    
            seen[key] = day
    
        elif (
            "dt" in day
            and "dt" not in seen[key]
        ):
    
            seen[key] = day
    
    merged_days = list(
        seen.values()
    )
    
    merged_days.sort(
        key=lambda x: (
            x.get("dt", 0),
            x.get("d", 0)
        )
    )
    
    new_days = []
    
    day_no = 1
    
    for day in merged_days:
    
        new_day = dict(day)
    
        new_day["d"] = day_no
    
        day_no += 1
    
        new_days.append(
            new_day
        )
    
        total_nett += (
            day.get(
                "n",
                0
            ) or 0
        )
    
        total_gross += (
            day.get(
                "g",
                0
            ) or 0
        )

    output = {}

    output.update(
        best_meta
    )

    output["rd"] = (
        earliest_rd
    )

    output["days"] = (
        new_days
    )

    output["tn"] = round(
        total_nett,
        2
    )

    if total_gross > 0:

        output["tg"] = round(
            total_gross,
            2
        )
        
        
    FORCE_YEAR.append(
        {
            "s": slug,
            "m": force_movie_name,
            "fy": base_year
        }
    )

    save_json(
        base_path,
        output
    )

    print(
        "KEEP:",
        base_path
    )
    
    for path, _ in files[1:]:
    
        print(
            "DELETE:",
            path
        )
    
        os.remove(
            path
        )


os.makedirs(
    "data/hindi",
    exist_ok=True
)

save_json(
    "data/hindi/forceyear_merged.json",
    sorted(
        FORCE_YEAR,
        key=lambda x: x["m"].lower()
    )
)

print(
    "Saved: data/hindi/forceyear_merged.json"
)

print(
    "Merge completed"
)
