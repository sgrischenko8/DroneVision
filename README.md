# Drone Vision Pipeline — Detection, Tracking & Onboard Safety Logic

A CPU-friendly, real-time computer-vision pipeline built for a (simulated) drone: YOLOv8
object detection, multi-object tracking, manual target lock, and a set of onboard "safety"
behaviors (thermal throttling, low-battery power saving) that all compete for the same
resources and are reconciled by a small policy layer.

The project runs against a webcam or a video file and displays an annotated live view
while logging every meaningful event to CSV with matching screenshots.

## Highlights

- **YOLOv8 (OpenVINO) detection + ByteTrack (Supervision) tracking**, with optical-flow
  interpolation between detection cycles to keep boxes smooth without running YOLO every frame.
- **Two model profiles** (320px "light" / 480px "full") that are hot-swapped depending on
  power-save state, both warmed up at startup to avoid a mid-stream OpenVINO compile stall.
- **Manual target lock ("FIRE mode", key `F`)** — locks onto the highest-confidence box,
  draws an offset vector to frame center, and tolerates brief detection dropouts before
  declaring the target truly lost.
- **Thermal safety controller** — reacts to simulated chip-temperature telemetry with a
  two-stage WARNING → CRITICAL response (pause, then permanently disable YOLO/tracking),
  logged and screenshotted at every step.
- **Power-save mode (key `L`)** — cuts detection frequency and swaps to the lighter model,
  either manually or automatically on low battery.
- **A policy-resolver layer** (`event_resolver.py`) that decides who wins when these
  independent modules want conflicting things at once (see [Design](#design--module-interactions) below) —
  none of the individual controllers know about each other.
- **Simulated drone telemetry** (battery drain, chip temperature) delivered asynchronously
  through a background thread, mimicking how a real telemetry/radio link would feed the
  main loop via `poll_events()`.
- **Unified CSV event log + JPEG screenshots** for every state transition (locks, losses,
  overheat, power save, low battery).

## Project structure

| File | Responsibility |
|---|---|
| `main.py` | Frame producer/consumer loop, model inference, tracking, orchestration of all controllers, UI (OpenCV window, banners, FPS). |
| `config.py` | All tunable constants: video source, detection/tracking thresholds, colors, thermal thresholds, telemetry simulation parameters, etc. |
| `tracked_object.py` | Converts Supervision's `sv.Detections` (parallel arrays, xyxy) into a list of simple `TrackedObject`s (one object per track, xywh) shared by `fire.py` and `main.py`. |
| `fire.py` | Manual target-lock controller ("FIRE", key `F`): lock/track/loss lifecycle, offset-vector drawing, grace period on temporary detection loss. |
| `thermal.py` | Chip-overheat state machine. Split into a pure `evaluate()` (decide) / `commit()` (apply) pair so its decisions can be deferred by the resolver without any awareness of *why*. |
| `power_save.py` | Toggles a longer detection interval / lighter model to save CPU/GPU under low battery or by operator request. |
| `telemetry.py` | Background thread simulating an async drone telemetry link (battery drain, chip temperature); real hardware would only need this file replaced. |
| `event_resolver.py` | Cross-module conflict resolution: FIRE defers thermal shutdowns; FIRE overrides power save and restores it afterward only if still justified. |
| `logger.py` | Single CSV writer + screenshot capture used by every module. |
| `cv_utils.py` | Small geometry helpers: bbox IoU, integer bbox conversion, frame-relative offset/scale computation. |
| `drawing.py` | All `cv2` drawing helpers: tracked-object boxes, FIRE lock box, translucent banners. |
| `display.py` | Aspect-ratio-safe window sizing and letterboxing (currently window sizing is disabled in `main.py` in favor of `WINDOW_AUTOSIZE`). |
| `download_model.py` | Exports `yolov8n.pt` to OpenVINO IR format — run this once before `main.py` to prepare the models it expects. |
| `qm.py` | One-off script to produce an INT8-quantized ONNX model via `onnxruntime.quantization`. |

## Design & module interactions

Several behaviors are intentionally decoupled so each file only knows about its own
lifecycle, with all cross-cutting policy centralized in `event_resolver.py`:

- **Thermal vs. FIRE** — `thermal.py` only ever proposes a `ThermalDecision` (pause /
  resume / disable). If a target is currently locked, the resolver withholds `commit()`,
  so the shutdown is *deferred, not skipped*: the same decision will be proposed again on
  the next temperature reading once FIRE ends.
- **FIRE vs. power save** — while a target is locked, power save is force-disabled
  (full detection rate/accuracy is needed for aiming) regardless of how it was enabled.
  When the lock is lost, power save is restored only if it's still independently justified
  (battery still low, or it was manually enabled before the lock started).
- **Thermal state is one-directional** — once YOLO/tracking is permanently disabled due to
  overheating, it does not come back on for the remainder of the run.

Both `fire.py` and `power_save.py` are written as self-contained, removable modules: each
file's docstring/comments state what to remove from `main.py` to drop that feature entirely.

## Controls

> All key presses only work with an English (US) keyboard layout — Cyrillic or other layouts won't register.

| Key | Action |
|---|---|
| `F` | Toggle target lock (locks onto the highest-confidence tracked object; no-op if already locked or nothing detected). |
| `L` | Toggle power-save mode. |
| `Q` | Quit. |

## Configuration

All tunables live in `config.py`, grouped by subsystem:

- Video source/output, detection interval, tracking/matching thresholds.
- Power-save detection interval.
- CSV log path / screenshot directory.
- Bounding-box and banner colors (BGR).
- FIRE grace period for temporary detection dropout.
- Simulated telemetry: battery drain rate/threshold, chip-temperature spike/escalation
  chances and ranges.
- Thermal thresholds (`TEMP_WARNING_MIN_C`, `TEMP_CRITICAL_C`) and the WARNING pause
  duration.

## Requirements

- Python 3.9+
- `opencv-python`
- `numpy`
- `ultralytics`
- `supervision`
- `openvino`
- A webcam, or a video file path set in `config.VIDEO_SOURCE`

Install (example):

```bash
pip install -r requirements.txt
```

## Preparing the models

`main.py` expects OpenVINO IR models at `yolov8n_320_openvino_model` and
`yolov8n_480_openvino_model`. Before running `main.py`, run:

```bash
python download_model.py
```

## Running

```bash
python download_model.py
python main.py
```

An OpenCV window opens showing the live annotated feed (bounding boxes, trajectories,
FPS counter, and status banners for battery/thermal/power-save state). Detected events
are appended to `detections_log.csv`, with screenshots saved under `screenshots/`.

## Notes

- There is no physical drone: `telemetry.py` simulates the async telemetry channel. Swapping
  in real hardware only requires replacing `telemetry.py`'s internals — the event names and
  shapes (`LOW_BATTERY`, `BATTERY_LEVEL`, `CHIP_TEMP`) are meant to stay the same.
- `qm.py` is a standalone utility/reference script and is not wired into the main pipeline.
