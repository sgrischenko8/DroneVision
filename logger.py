import os
import csv
import atexit
import queue
import threading
from datetime import datetime
import cv2
from config import CSV_LOG_PATH, SCREENSHOT_DIR, COLOR_LOST, COLOR_CONFIRMED
from cv_utils import compute_offset_and_scale

def init_csv_log():
    file_exists = os.path.isfile(CSV_LOG_PATH)
    if not file_exists:
        with open(CSV_LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "video_time_sec", "frame_idx", "event",
                "object_id", "class_name", "confidence",
                "dx_px", "dy_px", "z_percent", "screenshot"
            ])

# Файловий I/O виконується у фоновому потоці, щоб не блокувати основний
# (відео) потік. Черга зберігає порядок подій.
_log_queue = queue.Queue()
_logger_stop = threading.Event()
_logger_thread = None
_logger_lock = threading.Lock()

def _write_log_worker():
    # Фоновий worker для запису CSV та зображень
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    try:
        with open(CSV_LOG_PATH, "a", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)

            while not _logger_stop.is_set() or not _log_queue.empty():
                try:
                    item = _log_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                try:
                    screenshot_path = item["screenshot_path"]
                    if screenshot_path:
                        cv2.imwrite(screenshot_path, item["frame"])

                    writer.writerow(item["csv_row"])
                    csv_file.flush()
                except Exception as exc:
                    print(f"Помилка фонового логування: {exc}")
                finally:
                    _log_queue.task_done()
    except Exception as exc:
        print(f"Не вдалося запустити фоновий logger: {exc}")

def _ensure_logger_started():
    global _logger_thread

    with _logger_lock:
        if _logger_thread is None or not _logger_thread.is_alive():
            init_csv_log()
            _logger_stop.clear()
            _logger_thread = threading.Thread(
                target=_write_log_worker,
                name="logger-worker",
                daemon=True,
            )
            _logger_thread.start()

def close_logger():
    global _logger_thread

    with _logger_lock:
        if _logger_thread is None:
            return
        _logger_stop.set()
        thread = _logger_thread

    _log_queue.join()
    thread.join(timeout=2.0)

    with _logger_lock:
        if _logger_thread is thread:
            _logger_thread = None

atexit.register(close_logger)

def log_event(frame, bbox, event, frame_idx, video_time, object_id="", class_name="", confidence=None, take_screenshot=True):
    # спільна функція логування для всіх подій (FIRE, посадка, зміна режимів і т.д.)
    # bbox=None - якщо об'єкта в кадрі немає (наприклад SEARCHING_PAD)
    # take_screenshot=False варто ставити для подій що пишуться щокадру (TRACKING_PAD і т.п.),
    # щоб скріншот створювався тільки на переходах стану (інакше відбувається засмічування скріншотами)
    if bbox is not None:
        dx, dy, z_percent = compute_offset_and_scale(frame, bbox)
    else:
        dx = dy = z_percent = None

    now = datetime.now()
    ts_readable = now.strftime("%Y-%m-%d %H:%M:%S")

    screenshot_name = ""
    screenshot_path = ""

    if take_screenshot:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts_str = now.strftime("%Y%m%d_%H%M%S_%f")[:-3]
        screenshot_name = f"{ts_str}.jpg"
        screenshot_path = os.path.join(SCREENSHOT_DIR, screenshot_name)

        box_color = COLOR_LOST if event in ("TARGET_LOST", "LOST_PAD") else COLOR_CONFIRMED

        # Копія та нанесення підпису виконуються в основному потоці, але
        # важкий JPEG encode + запис на диск — у фоновому worker-і.
        snap = frame.copy()
        if bbox is not None:
            x, y, w, h = [int(v) for v in bbox]
            cv2.rectangle(snap, (x, y), (x + w, y + h), box_color, 2)
            label = f"{event}  {class_name} {'' if confidence is None else f'{confidence:.2f}'}  {ts_readable}"
            cv2.putText(snap, label, (x, max(0, y - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)
        else:
            cv2.putText(snap, f"{event}  {ts_readable}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)
    else:
        snap = None

    csv_row = [
        ts_readable, f"{video_time:.3f}", frame_idx, event,
        object_id, class_name, "" if confidence is None else f"{confidence:.4f}",
        "" if dx is None else f"{dx:.1f}",
        "" if dy is None else f"{dy:.1f}",
        "" if z_percent is None else f"{z_percent:.2f}",
        screenshot_name
    ]

    _ensure_logger_started()
    _log_queue.put({
        "frame": snap,
        "screenshot_path": screenshot_path,
        "csv_row": csv_row,
    })