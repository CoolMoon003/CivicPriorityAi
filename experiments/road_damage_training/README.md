# Road-damage training experiments

**Everything in this directory is experimental or historical. These artifacts are not the selected YOLO26 detector.** CivicPriorityAI's selected road-damage checkpoint is `models/YOLO26s_RDD_Base.pt`; integration into the application is pending a separate phase.

## Unified dataset YOLO11s attempt

- Dataset: local derived Unified Road Defect Dataset at `data/processed/road_damage_unified/`; configuration: `rdd_merged.yaml`.
- Images recorded in the run: 25,677 train and 4,509 validation. These are shared from the authoritative dataset and are not copied into this experiment.
- Classes: 0 Longitudinal Crack (D00), 1 Transverse Crack (D10), 2 Alligator Crack (D20), 3 Pothole (D40).
- Architecture: Ultralytics YOLO11s detection, initialized from `yolo11s.pt`.
- Recorded configuration: 20 epochs, 640 image size, batch 8, CPU, 4 workers, validation enabled, patience 100.
- Status: interrupted before completion. The user stopped the run because CPU training was taking many hours.
- Metrics: no completed validation metrics are present for this run. There is no `results.csv` or saved `best.pt`/`last.pt` in its artifact folder; no accuracy or mAP is claimed here.
- Preserved evidence: run `args.yaml` under `results/unified_yolo11s_interrupted/` and batch/label previews and plots under `plots/unified_yolo11s_interrupted/`.

The run configuration was captured under a nested `runs/detect/runs/...` path. The original image and label trees are not duplicated here. Historical config values are retained as recorded evidence even though the dataset has since moved.

## Earlier RDD2022 India experiments

`historical_RDD2022/` preserves a separate YOLO11n run on the RDD2022 India dataset, its v2 follow-up artifacts/configuration, the local base checkpoint, and a one-epoch smoke-test output. This is distinct from the interrupted Unified-dataset YOLO11s attempt. See [the audit](../../docs/road_damage_training_audit.md) for recorded configuration, split counts, and existing RDD2022 metrics. These older experiment checkpoints remain available because the current backend detector still points to the v1 RDD2022 checkpoint; replacing that backend configuration is part of the later integration phase.

## Layout

```text
road_damage_training/
  dataset/                         Dataset pointer/notes; no duplicate images
  model/yolo11s.pt                 YOLO11s initialization checkpoint
  results/unified_yolo11s_interrupted/  Run configuration and results files, if any
  plots/unified_yolo11s_interrupted/    Preserved run previews/plots
  historical_RDD2022/              Separate previous RDD2022 work
```
