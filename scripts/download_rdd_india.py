from huggingface_hub import HfApi, hf_hub_download
from pathlib import Path
from collections import Counter

REPO = "dronefreak/RDD2022"
OUT = Path("data/raw/RDD2022_India")

api = HfApi()

print("Getting file list from Hugging Face...")
files = api.list_repo_files(REPO, repo_type="dataset")

# Only India images and labels
india_files = [
    f for f in files
    if Path(f).name.startswith("India_")
    and (
        "/images/" in f
        or "/labels/" in f
    )
]

print(f"Found {len(india_files)} India image/label files.")

# Show counts
image_files = [f for f in india_files if "/images/" in f]
label_files = [f for f in india_files if "/labels/" in f]

print(f"Images : {len(image_files)}")
print(f"Labels : {len(label_files)}")

print("\nDownloading...")

for i, file in enumerate(india_files, 1):
    print(f"[{i}/{len(india_files)}] {file}")

    hf_hub_download(
        repo_id=REPO,
        filename=file,
        repo_type="dataset",
        local_dir=OUT,
    )

# Download dataset configuration
hf_hub_download(
    repo_id=REPO,
    filename="data/data.yaml",
    repo_type="dataset",
    local_dir=OUT,
)

print("\n===================================")
print("DOWNLOAD COMPLETE")
print("===================================")
print(f"Saved to: {OUT.resolve()}")
