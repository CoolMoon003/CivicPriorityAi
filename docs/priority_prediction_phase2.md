# Priority prediction and outcome recalibration

## Current architecture

Citizen image → YOLO class/severity/confidence → matched OSM road → shared feature builder → explainable `PriorityEngine` baseline → optional RandomForest priority prediction → admin decision/optimizer → recorded repair and verification outcome → future outcome-based training.

The existing `PriorityEngine` remains authoritative for its rule-based baseline and optimizer input. The AI prediction is separately named and is never written over `Complaint.priority_score`.

The initial ML target is the current `PriorityEngine` score because the database does not yet contain enough numeric repair-outcome labels. This is a **baseline-derived prototype**, not ground truth and not a model of repair success. The existing `Repair` and `Outcome` records capture completion, cost, and verification context; they do not currently provide a validated numeric priority/outcome target. New fields and migrations were therefore not needed. Actual outcome records must be reviewed/defined before they are used as labels.

## Feature/data notes

`priority_features_v1` is the single fixed-order builder used by training, inference, and API prediction. It uses persisted damage class, severity and confidence; matched road classification/length/lanes/speed; existing `near_*` road flags; disjoint older/recent unresolved complaint counts; district accident/death totals; and the rule baseline. Detection counts/box coverage are not stored on the complaint and are omitted. Population is `null` with a missingness flag: the ward dataset has no defensible complaint/road-to-ward join. Accident values are explicitly district-level context repeated in the road-feature CSV, never claims about an individual road.

## Training and model versioning

Run `..\.venv\Scripts\python.exe scripts\train_priority_model.py` from `frontend`, or `.\.venv\Scripts\python.exe scripts\train_priority_model.py` from the project root. It evaluates with leave-one-out cross-validation and reports MAE, RMSE, and R² against the recomputed baseline. These metrics measure baseline reproduction only. The final model and metadata are written to versioned files under `models/priority/`; `current.json` points inference at the latest version. `--metrics-only` reproduces metrics without saving a model.

The inference service loads the model once. If the artifact or optional `joblib`/scikit-learn dependency is unavailable, APIs return an explicit unavailable status and the baseline still works. The current UI does not label global feature importance as an individual explanation; it says per-complaint contributions are unavailable and continues to show the baseline's evidence explanations separately.

Once enough real, consistently defined repair outcomes exist, a later training version can select those records as targets and mark `training_type` as `outcome-trained`. Until then, do not describe this prototype as predicting actual repair success.
