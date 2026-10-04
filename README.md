# CivicPriority AI

### Equity-Aware, Budget-Constrained Road Infrastructure Repair Optimization with Outcome-Based Recalibration

## Repository map and model status

This repository contains the original source for a student/hackathon civic-tech prototype focused on Vellore, Tamil Nadu. Runtime model weights, full datasets, local databases, uploads, and generated artifacts are not included in the public source repository. The project source code is licensed under MIT; that license does not apply to third-party models, datasets, public-data extracts, or other separately licensed material. See [Third-party licenses and data attribution](#third-party-licenses-and-data-attribution).

**Current active detector:** `backend/ai/road_damage_detector.py` loads the pretrained `models/YOLO26s_RDD_Base.pt` checkpoint for inference without retraining. The detector validates its four-class ID mapping and returns standard Python box detections while preserving the complaint flow's existing primary damage, confidence, and application-assigned severity fields. The model detects damage; CivicPriority's separate priority engine scores repair urgency using its existing policy.

### Top-level structure

```text
backend/                         FastAPI application and services
frontend/                        Vite/React application
models/                          Active model assets and priority model
data/
  raw/RDD2022_India/             Original RDD2022 India dataset
  processed/road_damage_unified/ Derived four-class Unified dataset
  sample/road_damage/            Small road-damage test/demo sample
  public/, vellore/, uploads/    Civic data and files at paths used by app/scripts
experiments/road_damage_training/ Historical training attempts and artifacts
scripts/                         Data, audit, training, and utility scripts
runs/inference/                  Saved inference/demo outputs
docs/                            Project notes and training audit
tests/                           Automated tests
.venv/                           Existing local Python environment (preserved)
```

The civic priority workflow and public-data sources are described below. The road-damage detector supplies image evidence; priority remains a separate scoring/optimization workflow.

## Road-damage model and experiment

The selected checkpoint, `models/YOLO26s_RDD_Base.pt`, is a YOLO26s detector reported by its [Hugging Face model card](https://huggingface.co/TamAko783/YOLO26s_RDD_Base) as trained on the same Unified Road Defect Dataset and its four-class schema: 0 D00 Longitudinal Crack, 1 D10 Transverse Crack, 2 D20 Alligator Crack, 3 D40 Pothole. The card reports mAP@50 0.687, mAP@50–95 0.372, precision 0.731, and recall 0.609 on its 4,509-image held-out validation set. These are published model-card figures, not a local rerun. The card declares AGPL-3.0; the derived dataset has mixed-source attribution terms, so consult its [dataset card](https://huggingface.co/datasets/TamAko783/Unified_Road_Defect_Dataset) and underlying source terms before redistribution.

The separate YOLO11s experiment on that Unified dataset was configured for 20 epochs on CPU and stopped before completion because it was taking many hours. Its available artifacts do not contain completed validation metrics or a saved checkpoint. The attempt, configuration, and visual artifacts are preserved in [`experiments/road_damage_training/`](experiments/road_damage_training/README.md); earlier RDD2022 India YOLO11 experiments are also kept separately there. This is historical experimental training evidence and is not the active detector. YOLO26 was not trained by this project; the pretrained checkpoint is used directly for inference.

CivicPriority AI is a Vellore road-maintenance demo that helps administrators review and prioritize reported road damage using image detections, mapped roads, and available public context.

## Current workflow

Citizen complaint and uploaded image → YOLO road-damage detection → nearest OSM road matching → available facility/road/district context → deterministic `PriorityEngine` rule-based baseline → optional RandomForest AI prediction → admin review and priority queue → budget optimizer → technician assignment and repair → recorded completion/verification outcomes → future outcome-based recalibration.

## Two separate priority signals

- **Rule-based baseline:** the existing explainable `PriorityEngine` score. It remains authoritative for the current admin queue and budget optimizer. Its scoring formula and weights are unchanged.
- **AI prediction:** optional `priority_model_v1`, a RandomForestRegressor trained to reproduce baseline scores from five existing complaint records. The model does not replace or overwrite baseline scores.
- **Future outcome model:** not active. Repair completion, costs, notes, and verification are recorded in the existing repair/outcome workflow, but they do not yet define a validated numeric target for priority. More genuine outcomes and an explicit target definition are required before outcome-trained recalibration.

The prototype's leave-one-out metrics are **MAE 8.623, RMSE 13.4687, R² 0.2409 against baseline-derived prototype labels**. These metrics do not measure repair prediction, real-world priority accuracy, or infrastructure outcome prediction accuracy. The training sample is five complaints and should not be interpreted as generalizable performance.

Model files:

- `models/priority/priority_model_v1.joblib`
- `models/priority/priority_model_v1.json`
- `models/priority/current.json`

Train/version the baseline-derived prototype with:

```powershell
.\.venv\Scripts\python.exe scripts\train_priority_model.py
```

Training uses existing complaint records and the shared `priority_features.py` builder. It does not create complaints or outcome records. Model loading/inference is optional: a missing or failing model is reported as unavailable while the rule-based baseline continues to work.

## Repairs and outcomes

Technicians explicitly move assigned work through `IN_PROGRESS` and `REPAIRED`, then submit actual completion notes and optional recorded cost. An admin can record verification or request rework using the existing repair verification endpoint. No work is marked complete automatically. Existing `Repair` and `Outcome` records are reused; no extra outcome fields are fabricated. Future training must define a meaningful numeric target from genuine records before it can be described as outcome-trained.

## Data scope and limitations

- YOLO provides image-level damage-class evidence. Detection counts and bounding-box coverage are not persisted on complaints and are not used as model features.
- OSM features describe the matched road/network segment; nearby facility flags are the project's existing proximity evidence.
- Accident and death values are **district-level context**, not evidence of incidents on a particular road.
- Ward population is available as ward-level data, but there is no defensible complaint/road-to-ward mapping. Complaint-level population remains unavailable.
- Current complaint ownership and role workspaces are demo identity mechanisms, not authenticated accounts.
- Some records are development/demo submissions; they should not be presented as independently verified civic reports.

## Public data provenance

These are the existing sources used by the application; this phase did not download a new government dataset.

| Dataset | Publisher/source and link | Geographic level / period | Fields used and limits |
|---|---|---|---|
| Vellore road network and mapped public facilities | OpenStreetMap contributors; [ODbL and attribution](https://www.openstreetmap.org/copyright). Local extracts are built with OSMnx. | Road/network and mapped feature coverage for Vellore; the local extract timestamp is not recorded. | OSM road class, geometry, mapped length/lanes/speed where present, and mapped amenity features used for existing facility-nearby flags. OSM is community mapping and completeness varies; it is not a municipal asset register. |
| Tamil Nadu road accidents and deaths | Tamil Nadu State Transport Authority's [Road Accident Analysis in Tamil Nadu, 2021–2023, Table 5](https://tnsta.gov.in/pdfpage/pdfpage_en_4LPhMMh_2024_05_29.pdf), citing SCRB; the local CSV corresponds to Vellore values 819/976/992 accidents and 246/294/328 deaths. The same resource is indexed by [OpenCity](https://data.opencity.in/dataset/tamil-nadu-road-accidents-reports/resource/764579ad-22e0-4f27-a694-34d0d2f843ea). | District/city totals for 2021–2023. | Yearly accident/death totals only. This is district context, never road-level evidence; later statistical releases may use changed district boundaries or revised counts. |
| Vellore Corporation ward population | [Vellore Corporation population page](https://www.tnurbantree.tn.gov.in/vellore/population/), Tamil Nadu urban local body portal. | 60 ward rows; the page does not state a reference year. | Ward male/female/total fields. No road-to-ward crosswalk exists, so these totals are not attached to individual roads or complaints. |
| Unified Road Defect Dataset images used in synthetic demo examples | Unified dataset from the project model/dataset source records; consult the local dataset card and upstream mixed-source attribution terms before redistributing. | Images are validation samples, including multiple RDD source subsets; they are not geolocated to Vellore. | The demo refresh reads the existing labels, chooses visible examples, requires a matching YOLO26 detection, and stores a separate annotated copy. Original dataset images and label files remain unchanged. |

The local `nammATN_civic_issues.geojson` and `vellore_civic_issues.geojson` have no source URLs or provenance metadata. They are not used by the priority model, and the admin summary reports their counts as unavailable rather than presenting them as public complaint statistics.

Local road, facility, accident, and ward extracts are not included in the public source repository. Some are generated from larger sources, and redistribution terms/provenance for every local copy have not been established. Use the documented source links and scripts, and review the upstream terms before obtaining or redistributing data.

## Third-party licenses and data attribution

The [MIT `LICENSE`](LICENSE) covers only original CivicPriorityAI source code and its accompanying original documentation. It does not grant rights to third-party material.

- **YOLO26s road-damage checkpoint:** The upstream [TamAko783 model card](https://huggingface.co/TamAko783/YOLO26s_RDD_Base) declares AGPL-3.0 and credits the Ultralytics YOLO26 model. The checkpoint is excluded from this repository. Obtain and use it only after reviewing the upstream license and any obligations that apply to your use; this project's MIT license does not relicense the checkpoint.
- **Road-damage datasets and derived samples:** The Unified Road Defect Dataset combines RDD-2022, UAV-PDD2023, and RoadDamageVision under mixed-source terms. Its [dataset card](https://huggingface.co/datasets/TamAko783/Unified_Road_Defect_Dataset) and local provenance documentation require checking the original terms. In particular, the RDD-2022 and UAV-PDD2023 reuse terms are not verified here. No redistribution rights for the combined dataset, source images/labels, or derived demo images are claimed. Dataset files and image assets are excluded from this source repository.
- **Public Vellore contextual data:** OpenStreetMap-derived road/facility extracts are subject to ODbL and attribution requirements; consult [OpenStreetMap attribution and license information](https://www.openstreetmap.org/copyright). The cited Tamil Nadu accident statistics and Vellore ward population source remain subject to their publishers' terms and attribution. These contextual sources are not covered by the project MIT license. Local extracts are not included unless explicitly listed as safe, attributed source assets.
- **Unverified civic-issues files:** `nammATN_civic_issues.geojson` and `vellore_civic_issues.geojson` have no verified provenance and are excluded from Git.

Review each upstream source's current license, attribution, and redistribution conditions before obtaining or redistributing third-party assets. No blanket permission to redistribute those assets is implied by this repository.

## Synthetic demo records

Run `scripts/seed_demo_data.py` without arguments for a read-only model-backed dry-run, or with `--apply` to append enough marked records to reach 50 total. New seed images come from the local Unified validation dataset, are selected by visible ground-truth boxes, and must have a matching YOLO26 detection. To refresh existing marked records in place, run `scripts/refresh_demo_images.py` first without arguments for a dry-run, then use `--apply` after reviewing the plan. The refresh found 44 explicitly marked image-backed demo records and replaced their photos while preserving complaint IDs, statuses, assignments, repairs, and outcomes. It selected 11 examples per class; 42 had confirmed matching detections and 2 pothole examples remained possible/uncertain. Seventeen unmarked complaints were preserved. These counts document a demo-data refresh and are not measures of model accuracy. The selected photos are benchmark images, not citizen submissions or geolocated evidence for the synthetic Vellore points.

Damage severity is an application policy derived from the class: pothole/alligator crack are HIGH and longitudinal/transverse crack are MEDIUM. YOLO predicts class and confidence, not severity. The detector exposes three confidence states: **confirmed** at confidence >= 0.25, **possible / AI uncertain** from 0.10 to below 0.25, and **no reliable detection** below 0.10. Defaults are centralized in `backend/ai/detection_policy.py`; override with `CIVIC_DAMAGE_CONFIRMED_THRESHOLD` and `CIVIC_DAMAGE_POSSIBLE_THRESHOLD`. `CIVIC_ROAD_DAMAGE_CONFIDENCE` remains a backwards-compatible confirmed-threshold override, and `CIVIC_DAMAGE_INFERENCE_SIZE` defaults to 640. If the normal pass has no candidate at or above the possible threshold, the detector makes one conditional retry at `CIVIC_DAMAGE_FALLBACK_INFERENCE_SIZE` (default 1280); set it to `0` to disable this retry. This fallback preserves the normal confidence policy and is not a global confidence-threshold reduction.

Possible evidence keeps its predicted class and class-policy severity but is labeled uncertain, and its damage component is discounted by the detection confidence. No reliable evidence is normalized to unknown with zero confidence; stale legacy class/severity fields below the possible threshold cannot increase priority. The existing priority weights and bands are unchanged. API/UI labels keep AI confidence, damage severity, and overall priority separate. Confidence is not correctness, and uncertain detections require human verification.

Run the CPU-only heavy-image, multi-resolution diagnostic (diagnostic conf=0.001 does not change production thresholds):

```powershell
.\.venv\Scripts\python.exe scripts\diagnose_heavy_image.py
```

Run the small India/China source-stratified validation diagnostic and policy/priority tests:

```powershell
.\.venv\Scripts\python.exe test_india_china.py --per-class-origin 2
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The stratified diagnostic matches predicted class/boxes against labels at IoU >= 0.50 for confidence thresholds 0.10, 0.15, 0.20, and 0.25. It does not run inference on the full 4,509-image validation set.

For older records, confidence and class fields are normalized against the centralized confidence policy. On 2026-09-29, 44 marked synthetic records were updated with Unified validation images and matching YOLO26 class evidence (11 per supported class). Each now has a generated annotated image. Seventeen unmarked records were not edited. Ground-truth labels are used to select examples and are not copied as model predictions.

Demo repair/verification records have explicit `SYNTHETIC DEMO` notes and no repair-cost values. They are workflow examples only, not genuine repair outcomes, and are not used to train `priority_model_v1`. The seed script creates a one-time SQLite backup before writes. Re-running it does not duplicate complaints once the 50-record target is reached. The admin overview labels the workspace as a mix of pre-existing development/demo rows and explicitly synthetic examples, not an official government complaint feed.

## Image handling

Citizen uploads are stored under `data/uploads` with generated filenames and served by FastAPI at `/uploads`. When YOLO26 returns detections at or above the possible threshold, a separate annotated sidecar is written under `data/uploads/annotated`; otherwise the original image is shown with �No reliable AI detection.� The annotation boxes, labels, and confidence values come from the detector output. Unified demo originals and annotations are stored under `data/uploads/demo_unified/` and its `annotated/` subfolder.

Road feature extracts and other local context data are generated/downloaded artifacts and are excluded from Git. The corresponding scripts and source references are included; regenerate local inputs after reviewing each source's terms.

## Run locally

Use the project's working Python 3.11 virtual environment.

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

Frontend in another terminal:

```powershell
cd frontend
npm.cmd run dev
```

The frontend opens the role-selection screen and uses the three demo workspaces: Citizen, Admin, and Technician.

## Useful endpoints

- `GET /health` (lightweight service check; does not run inference or query the database)
- `POST /complaints/`
- `GET /admin/complaints` and `GET /admin/complaints/{complaint_id}`
- `GET /admin/priorities` and `GET /admin/priorities/{complaint_id}`
- `GET /citizen/profiles/{user_id}` and citizen complaint/profile routes under `/citizen`
- Technician work and status routes under `/technicians`
- Repair completion and verification routes under `/outcomes`
- `GET /admin/optimization?budget=<INR>`

## Complaint deletion

The admin delete endpoint removes only the selected complaint and its associated repair/outcome rows. It removes image files only when the path is a generated UUID-named direct citizen upload, no other complaint references it, and the file is under `data/uploads`; dataset and demo assets are retained. The admin detail UI requires typing `DELETE` in a confirmation dialog before sending the existing delete request. This is accidental-deletion protection, not authentication or authorization. Citizen and technician views have no delete action. The project role picker is not authentication.


## Environment configuration

Backend settings are read from the process environment. For local development, copy `.env.example` to `.env` and start Uvicorn with `--env-file .env`. `.env` is ignored by Git.

| Variable | Required | Purpose |
|---|---|---|
| `CORS_ORIGINS` | Set for a separately hosted frontend | Comma-separated exact browser origins. Local defaults allow the Vite dev server only. |
| `CIVIC_DATA_DIR` | No | Base directory for the SQLite database, uploads, and annotations; defaults to repository `data/`. Set to a persistent mount such as `/var/data` on Render. |
| `CIVIC_ROAD_GRAPHML` | Required for backend startup if default file is absent | Vellore OSM road graph path; defaults to `data/vellore/vellore_drive_network.graphml`. |
| `CIVIC_ROAD_FEATURES_GEOJSON` | Required for backend startup if default file is absent | Road feature GeoJSON path; defaults to `data/processed/vellore_road_features.geojson`. |
| `CIVIC_ROAD_FEATURES_CSV` | No | Optional road feature CSV path used by priority context; defaults to `data/processed/vellore_road_features.csv`. |
| `DUPLICATE_DISTANCE_METERS` | No | Location warning radius; defaults to 5 metres. |
| `CIVIC_ROAD_DAMAGE_MODEL` | No, if the default checkpoint is present | Model file path; defaults to `models/YOLO26s_RDD_Base.pt`. |
| `CIVIC_DAMAGE_CONFIRMED_THRESHOLD` | No | Defaults to 0.25. |
| `CIVIC_DAMAGE_POSSIBLE_THRESHOLD` | No | Defaults to 0.10. |
| `CIVIC_ROAD_DAMAGE_CONFIDENCE` | No, legacy alias | Confirmed threshold fallback when the newer variable is unset. |
| `CIVIC_DAMAGE_INFERENCE_SIZE` | No | Defaults to 640. |
| `CIVIC_DAMAGE_FALLBACK_INFERENCE_SIZE` | No | Defaults to 1280; set to 0 to disable the conditional fallback pass. |

By default, SQLite is stored at `data/civic_priority.db` and complaint images/annotations below `data/uploads`. Set `CIVIC_DATA_DIR` to a persistent directory to relocate all three together. Complaint image database keys remain `data/uploads/...` and resolve under the configured data directory, preserving compatibility with existing local records.

The frontend accepts `VITE_API_BASE_URL`, which is public browser configuration and must contain only the API origin, for example `https://api.example.org`. Set it in the Vercel project environment for production. Local development defaults to `http://127.0.0.1:8000`.

## Install and run

Use Python 3.11 and the project virtual environment. Install backend requirements only when provisioning a new environment; the model/runtime dependencies are large.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000 --env-file .env
```

In another terminal:

```powershell
cd frontend
npm ci
npm.cmd run dev
```

The YOLO26 checkpoint is excluded from Git. Obtain it from the upstream model source linked above, review the upstream model license and dataset terms, then set `CIVIC_ROAD_DAMAGE_MODEL` or place the checkpoint at the default path. Do not commit the checkpoint unless its license and Git hosting limits have been reviewed.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm.cmd run lint
npm.cmd run build
```

## Deployment guidance

### Demo deployment: Vercel + Render

This is a hackathon/demo deployment, not a municipal production service.

- **Frontend:** deploy `frontend/` to Vercel as a Vite static site. Build with `npm run build`, output `dist`, and set the public `VITE_API_BASE_URL` to the Render API origin.
- **Backend:** deploy the repository root to Render with Python 3.11 (selected by `.python-version`), build command `pip install -r requirements.txt`, and start command `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`. The module is `backend.app.main` and its ASGI object is `app`.
- **CORS:** set `CORS_ORIGINS` on Render to the exact Vercel origin, such as `https://your-project.vercel.app`; do not use `*`. Local development origins remain the default when the variable is unset.
- **Persistent files:** attach a Render persistent disk and set `CIVIC_DATA_DIR` to its mount path (for example `/var/data`). This keeps the SQLite database, citizen uploads, and generated annotations across restarts. SQLite and local file storage are prototype storage, not appropriate for real citizen data or multi-instance production use.
- **Road context inputs:** the backend currently loads the Vellore road graph and road-feature GeoJSON during import. They are excluded from Git, so provision them on the service disk and set `CIVIC_ROAD_GRAPHML` and `CIVIC_ROAD_FEATURES_GEOJSON` to their paths. The optional `CIVIC_ROAD_FEATURES_CSV` enables the road-feature lookup used in priority context. Without the required graph and GeoJSON files, priority scoring degrades gracefully but the API starts successfully. Review OSM attribution/ODbL terms when provisioning these extracts.
- **Model:** `models/YOLO26s_RDD_Base.pt` is intentionally excluded from Git. The detector does not download it per request and the app can start without it; road-damage inference remains unavailable until the checkpoint is separately provisioned in storage and `CIVIC_ROAD_DAMAGE_MODEL` points to it. Follow the upstream model license and dataset terms; no public download URL is implied here.

Production citizen service would require real authentication/authorization and persistent database/object storage. Do not use this SQLite/local-filesystem demo with real citizen data.

### Vercel frontend

The React frontend is a Vite static site. In Vercel, set the project root to `frontend`, use `npm run build`, and publish `dist`. Set `VITE_API_BASE_URL` to the HTTPS origin of the separately hosted API. Routes use URL hashes (`#/...`), so they do not require a server-side SPA rewrite. Vercel environment variables prefixed `VITE_` are embedded in public JavaScript.

### Backend and persistent services

Vercel supports Python functions, including FastAPI, but this backend is not a drop-in Vercel function: it has no Vercel function entry adapter, it writes uploads/annotations beside the app, and it stores SQLite locally. Vercel function filesystems are read-only apart from temporary `/tmp` scratch space, so those writes are not durable. Host FastAPI on a persistent service with a compatible Python 3.11 runtime and CPU/memory budget for PyTorch and YOLO26; mount durable storage at the project `data/` path and make the licensed model checkpoint available through persistent/model storage. Configure `CORS_ORIGINS` to the exact Vercel origin. Use a managed database and object storage only after adding and validating the required adapters; the current code does not provide those adapters. See [Vercel's Vite guide](https://vercel.com/docs/frameworks/frontend/vite), [Python runtime docs](https://vercel.com/docs/functions/runtimes/python), and [filesystem guidance](https://vercel.com/docs/functions/runtimes).

The frontend can be deployed independently, but the full application is not production-ready for real citizen data until API authentication/authorization is added. The role selector is only a UI choice, citizen IDs are not proof of identity, and most admin/technician/profile/repair routes currently lack authorization.

## Limitations and disclosure

- This project is a prototype/demo; it is not operated, endorsed, or integrated with Vellore Corporation or another government authority.
- Synthetic/demo complaint records and benchmark images are examples, not verified reports of local defects. Citizen-submitted complaints are separate user submissions but are not independently verified by the software.
- YOLO26 output is uncertain image analysis and requires human review. Published model-card metrics are upstream-reported, not a local reproduction.
- Priority scores are decision support, not a repair commitment. Priority weights are prototype design parameters, not validated municipal policy; the optimizer does not establish an optimal real-world municipal allocation. Public-context coverage is incomplete; accident totals are district-level, and population is not mapped to complaints/roads.
- Outcome records are captured, but validated outcome-based recalibration is future work; current priority remains the existing rule-based engine.
- The MIT license applies only to original CivicPriorityAI source code. The model declares AGPL-3.0 and the road-damage dataset has mixed upstream terms; those materials are excluded, and their individual terms must be reviewed before separate redistribution.
