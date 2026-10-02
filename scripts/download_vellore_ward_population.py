import pandas as pd
import os

URL = "https://www.tnurbantree.tn.gov.in/vellore/population/"
OUT = "data/public/vellore_ward_population.csv"

print("=" * 60)
print("BUILDING CLEAN VELLORE WARD POPULATION DATA")
print("=" * 60)

df = pd.read_html(URL)[0]

records = []

# Groups of 15 wards:
# 1-15, 16-30, 31-45, 46-60
groups = [
    (2, 3, 4, 5),       # ward row, male, female, total
    (6, 7, 8, 9),
    (10, 11, 12, 13),
    (14, 16, 15, 17),   # last group has swapped labels in source HTML
]

for ward_row, male_row, female_row, total_row in groups:
    wards = df.iloc[ward_row].tolist()
    males = df.iloc[male_row].tolist()
    females = df.iloc[female_row].tolist()
    totals = df.iloc[total_row].tolist()

    for col in range(1, 16):
        ward = str(wards[col]).strip()

        if ward == "nan":
            continue

        records.append({
            "ward": int(float(ward)),
            "male": float(males[col]),
            "female": float(females[col]),
            "total": int(float(totals[col]))
        })

result = pd.DataFrame(records).sort_values("ward").reset_index(drop=True)

os.makedirs("data/public", exist_ok=True)
result.to_csv(OUT, index=False)

print("\nClean dataset:")
print(result.to_string(index=False))

print("\n" + "=" * 60)
print("VALIDATION")
print("=" * 60)

print("Wards:", len(result))
print("Population:", result["total"].sum())
print("Male:", round(result["male"].sum(), 2))
print("Female:", round(result["female"].sum(), 2))

expected = 504079
actual = result["total"].sum()

print("Expected official total:", expected)
print("Calculated total:", actual)

if actual == expected:
    print("VALIDATION: PASS")
else:
    print("VALIDATION: CHECK REQUIRED")

print("\nSaved:")
print(OUT)
