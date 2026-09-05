# --- джерело відео ---
VIDEO_SOURCE = "test_video.mp4"
# VIDEO_SOURCE = 0   # 0 = веб-камера, або шлях до файла ("test_video.mp4")
WINDOW_NAME = "Data Fusion / Tracking"

# --- детекція / трекінг ---
DETECT_INTERVAL = 3
TRAJ_SECONDS = 3.0           # скільки секунд зберігаємо траєкторію
CONF_THRESHOLD = 0.4
MATCH_DIST_PX = 80           # запасний варіант, якщо IoU нульовий - зіставляємо по відстані центрів
MATCH_IOU_THRESHOLD = 0.3    # основний критерій зіставлення детекції з треком
DUP_MERGE_IOU = 0.5          # якщо новий детект сильно перекриває існуючий трек того ж класу - це той самий об'єкт
TRACKER_TYPE = "CSRT"
CONNECTION_TIMEOUT = 2.0     # секунд без кадрів = вважається, що зв'язок втрачено

CONFIRM_COUNT_FOR_LOG = 3
MAX_MISSED_DETECTIONS = 2
FPS_WINDOW = 10              # раз на скільки кадрів перераховуємо FPS
POWER_SAVE_FPS_WINDOW = 20
POWER_SAVE_DETECT_INTERVAL = 15

# --- логи ---
CSV_LOG_PATH = "detections_log.csv"
SCREENSHOT_DIR = "screenshots"

# --- кольори рамок (BGR) ---
COLOR_CONFIRMED = (0, 140, 255)
COLOR_LOST = (0, 0, 255)
COLOR_PAD = (255, 200, 0)
COLOR_WARNING = (0, 255, 255)
COLOR_CRITICAL = (0, 0, 255)
COLOR_LOCK = (0, 0, 255)

# --- захват цілі (клавіша F) ---
FIRE_LOCK_LOST_GRACE_SEC = 3.0  # скільки секунд ціль може бути тимчасово втрачена, перш ніж рахуємо TARGET_LOST

# --- посадка на маркер (клавіша P) ---
ARUCO_DICT = "DICT_4X4_50"
TOUCHDOWN_Z_PERCENT = 70.0
PAD_LOST_FRAMES = 10

# --- телеметрія дрона (симуляція) ---
TELEMETRY_CHECK_INTERVAL_SEC = 1.0

TELEMETRY_BATTERY_START_PERCENT = 100.0
TELEMETRY_BATTERY_DRAIN_PERCENT_PER_SEC = 1.0
TELEMETRY_LOW_BATTERY_THRESHOLD_PERCENT = 70.0

TELEMETRY_CHIP_TEMP_NOMINAL_C = 45.0
TELEMETRY_CHIP_TEMP_SPIKE_CHANCE_PER_CHECK = 0.1
TELEMETRY_CHIP_TEMP_ESCALATE_CHANCE_PER_CHECK = 0
TELEMETRY_CHIP_TEMP_WARNING_RANGE = (80.0, 90.0)
TELEMETRY_CHIP_TEMP_CRITICAL_RANGE = (91.0, 100.0)

TEMP_WARNING_MIN_C = 80.0
TEMP_WARNING_MAX_C = 90.0
TEMP_CRITICAL_C = 90.0
WARNING_YOLO_PAUSE_SEC = 5.0