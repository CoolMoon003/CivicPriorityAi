# Road damage detector training audit

## Existing checkpoint

`experiments/road_damage_training/historical_RDD2022/road_damage_v1/weights/best.pt` is YOLO11n detection (181 layers, approximately 2.59M parameters), initialized from the local pretrained `yolo11n.pt`. Its recorded run used RDD2022 India, 30 epochs, 640px images, batch 2, CPU, zero workers, no image cache, seed 42, validation enabled, and Ultralytics `optimizer=auto`. The run recorded `patience=100`, so the 30-epoch limit ended before early stopping could act. It used the `valid` split for epoch validation; `test` was not used for fitting.

Recorded augmentation settings were Ultralytics defaults: mosaic 1.0 with mosaic closed for the last 10 epochs, horizontal flip 0.5, HSV (0.015/0.7/0.4), translate 0.1, scale 0.5; vertical flip, mixup, cutmix, degrees, shear, and perspective were disabled.

## Dataset audit

The local `data/raw/RDD2022_India/data/data.yaml` mapping is unchanged and correct: 0 longitudinal crack, 1 transverse crack, 2 alligator crack, 3 pothole. All audited images are 720×720.

| Split | Images | Empty/missing labels | Longitudinal boxes | Transverse boxes | Alligator boxes | Pothole boxes |
|---|---:|---:|---:|---:|---:|---:|
| Train | 5,368 | 3,166 | 1,103 | 50 | 1,428 | 969 |
| Valid | 1,172 | 707 | 223 | 11 | 307 | 202 |
| Test | 1,166 | 725 semantically empty | 229 | 7 | 286 | 201 |

There were no corrupt images or malformed/non-finite YOLO rows in the audit. Train and validation labels matched all image paths. Test has two `*- Copy.jpg` images with no same-named label; the corresponding unsuffixed label files are empty, so they are negative examples, but their filenames do not match. Some boxes extend beyond image edges while their normalized YOLO values remain valid; source labels were not changed. An annotated sample from each class was visually reviewed and boxes were located on the road surface.

Transverse cracks are severely underrepresented: 50 train boxes in 44 train images, versus 969–1,428 boxes in the other classes. On a fresh evaluation of the existing checkpoint against `valid` at 640px, aggregate precision was 0.4530, recall 0.2830, mAP50 0.1743, and mAP50–95 0.0801. Class AP50 was 0.1422 longitudinal, 0.00016 transverse, 0.3598 alligator, and 0.1950 pothole. Metrics for transverse are especially uncertain because validation has only 11 boxes in 10 images.

## Separate v2 experiment

`scripts/audit_rdd2022.py` reproduces the read-only dataset audit. `scripts/train_road_damage_v2.py` prepares a generated image-list manifest (it does not change original images or labels), repeats only existing transverse-labelled training images eight times, and fine-tunes from the existing best checkpoint. Its defaults are 30 epochs, patience 10, batch 8, 640px, CPU, and the same held-out validation split. Output is isolated at `experiments/road_damage_training/historical_RDD2022/road_damage_v2/`; this is historical experiment output; the backend continues to reference the preserved v1 checkpoint pending the next integration phase.

The RDD2022 benchmark is not a guarantee of performance on citizen uploads. The audited benchmark images are square, unwatermarked, forward-facing road frames; complaint #51 is a 646×475 RGB JPEG with visible stock-photo watermarking and wider framing. Its raw alligator-crack box was only 0.015596 confidence at 640px, below the application's 0.25 threshold. A watermarked, differently framed upload and the severe class imbalance are material domain/coverage limitations; genuine local complaint images are needed to evaluate or improve this domain gap.
