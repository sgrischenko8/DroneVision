import cv2
import time
import threading
from queue import Queue, Empty, Full
from ultralytics import YOLO
import supervision as sv
import numpy as np
from config import WINDOW_NAME,VIDEO_SOURCE, FPS_WINDOW, COLOR_WARNING, TELEMETRY_LOW_BATTERY_THRESHOLD_PERCENT, CONNECTION_TIMEOUT, CONF_THRESHOLD, MATCH_IOU_THRESHOLD
from drawing import draw_banners
from fire import FireController
from logger import log_event
from power_save import PowerSaveController
from telemetry import DroneTelemetry
from thermal import ThermalController
from event_resolver import resolve_reading, resolve_fire_activation, resolve_fire_frame
from tracked_object import build_tracked_objects

def frame_producer(video_path, queue, stop_event, end_of_stream_event):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Помилка: не вдалося відкрити джерело відео {video_path}")
        stop_event.set()
        return

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            print(f"Кінець відеофайлу досягнуто: {video_path}")
            end_of_stream_event.set()  # відеофайл закінчився
            break

        if video_path == 0:
            frame = cv2.flip(frame, 1)

        timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

        while not stop_event.is_set():
            try:
                queue.put((timestamp_ms, frame), timeout=0.1)
                break
            except Full:
                continue

    print(f"Потік читання завершено: {video_path}")
    cap.release()

def main():
    TIMING_OVERSIGHT = 0.01    
    
    model_light = YOLO("yolov8n_320_openvino_model", task="detect")
    model = YOLO("yolov8n_480_openvino_model", task="detect")

    # прогріваємо обидві моделі одразу, поки не почалось відео
    # (OpenVINO компілює граф під розмір входу тільки на першому inference,
    # без прогріву це вилазить лагом в момент переходу в power save)
    print("Прогрів моделей (YOLO light/full)...")
    model_light(np.zeros((320, 320, 3), dtype=np.uint8), imgsz=320, verbose=False, device="intel:cpu")
    model(np.zeros((480, 480, 3), dtype=np.uint8), imgsz=480, verbose=False, device="intel:cpu")

    frame_queue = Queue(maxsize=100)
    stop_event = threading.Event()
    end_of_stream_event = threading.Event()
    producer_thread = threading.Thread(target=frame_producer, args=(VIDEO_SOURCE, frame_queue, stop_event, end_of_stream_event), daemon=True)
    producer_thread.start()

    tracker = sv.ByteTrack()

    box_annotator = sv.BoxAnnotator(thickness=2)
    trace_annotator = sv.TraceAnnotator(thickness=2, trace_length=30)
    label_annotator = sv.LabelAnnotator(text_scale=0.5, text_thickness=1)

    frame_count = 0
    fps_frame_count = 0
    start_time = time.time()
    fps = 0

    print("Запуск пайплайну обробки... Натисніть 'q' для виходу.")
    detections = sv.Detections.empty()

    last_frame_time = time.time()
    is_video_lost = False
    new_clock_timer = time.monotonic()

    prev_gray = None
    prev_pts = None
    lk_params = dict(winSize=(15, 15), maxLevel=2,
                     criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)

    power_save = PowerSaveController()
    telemetry = DroneTelemetry()
    telemetry.start()
    last_telemetry_lines_battery = []  # текст банера по батареї
    battery_low = False  # використовується в resolve_fire_frame при поверненні з TARGET_LOST
    tracked_objects = []
    fire = FireController()
    thermal = ThermalController()

    while not stop_event.is_set():
        try:
            timestamp_ms, frame = frame_queue.get(timeout=0.05) 

            processed_time = time.monotonic() - new_clock_timer
            if timestamp_ms/1000 <= processed_time:
                if processed_time > TIMING_OVERSIGHT:
                    continue
            elif VIDEO_SOURCE != 0:
                time.sleep(timestamp_ms/1000 - processed_time)
            last_frame_time = time.time()
            
            if is_video_lost:
                print("Зв'язок відновлено!")
                is_video_lost = False
        except Empty:
            if end_of_stream_event.is_set() and frame_queue.empty():
                stop_event.set()
                break
            if time.time() - last_frame_time > CONNECTION_TIMEOUT:
                if not is_video_lost:
                    is_video_lost = True
                    print("УВАГА: Втрачено відеозв'язок!")
                continue
            else:
                continue

        if is_video_lost:
            emergency_frame = 0 * frame  # чорний екран замість кадру
            cv2.putText(
                emergency_frame, 
                "CRITICAL: VIDEO LOST!", 
                (50, 100), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                1, 
                (0, 0, 255), 
                3
            )
            cv2.imshow(WINDOW_NAME, emergency_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                stop_event.set()
                break
            continue

        frame_count += 1
        fps_frame_count += 1
        video_time = processed_time

        # телеметрія дрона:
        for msg in telemetry.poll_events():
            if msg["event"] == "LOW_BATTERY":
                log_event(frame, None, "LOW_BATTERY", frame_count, video_time, None,
                          class_name=f"battery={msg['battery_percent']}%", confidence=None,
                          take_screenshot=False)
                power_save.toggle(frame, frame_count, video_time)
            elif msg["event"] == "BATTERY_LEVEL":
                # приходить кожну перевірку, тому актуальний % береться саме звідси
                percent = msg["battery_percent"]
                battery_low = percent <= TELEMETRY_LOW_BATTERY_THRESHOLD_PERCENT
                if battery_low:
                    last_telemetry_lines_battery = [f"LOW BATTERY: {percent}%"]
                    log_event(frame, None, "BATTERY_LEVEL", frame_count, video_time, None,
                              class_name=f"battery={percent}%", confidence=None,
                              take_screenshot=False)
                else:
                    last_telemetry_lines_battery = []
            elif msg["event"] == "CHIP_TEMP":
                resolve_reading(thermal, msg["temp_c"], frame, frame_count, video_time, fire)

        active_detect_interval = power_save.active_detect_interval()

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if power_save.enabled:
            current_model = model_light
            current_imgsz = 320

        else:
            current_model = model
            current_imgsz = 480

        # детекція запускається не на кожному кадрі, а раз в N (N залежить від power save)
        if frame_count == 1 or frame_count % active_detect_interval == 0:
            results = current_model(frame, imgsz=current_imgsz, conf=CONF_THRESHOLD, iou=MATCH_IOU_THRESHOLD, verbose=False, device="intel:cpu")[0]

            detections = sv.Detections.from_ultralytics(results)
            
            detections = tracker.update_with_detections(detections)
            if len(detections) > 0:
                centers = []
                for bbox in detections.xyxy:
                    cx = (bbox[0] + bbox[2]) / 2.0
                    cy = (bbox[1] + bbox[3]) / 2.0
                    centers.append([[cx, cy]])
                prev_pts = np.array(centers, dtype=np.float32)
            else:
                prev_pts = None
            
            prev_gray = gray.copy()
        else:
            if prev_gray is not None and prev_pts is not None and len(prev_pts) > 0:
                # Optical flow визначає зміщення точок між кадрами та застосовує його до bounding boxes
                curr_pts, status, err = cv2.calcOpticalFlowPyrLK(prev_gray, gray, prev_pts, None, **lk_params)

                new_xyxy = []
                valid_idx = []

                for i in range(len(curr_pts)):
                    if status[i][0] == 1:  # точку знайдено
                        dx = curr_pts[i][0][0] - prev_pts[i][0][0]
                        dy = curr_pts[i][0][1] - prev_pts[i][0][1]
                        
                        bbox = detections.xyxy[i].copy()
                        bbox[0] += dx
                        bbox[1] += dy
                        bbox[2] += dx
                        bbox[3] += dy
                        new_xyxy.append(bbox)
                        valid_idx.append(i)
                
                if len(valid_idx) > 0:
                    detections = sv.Detections(
                        xyxy=np.array(new_xyxy),
                        confidence=detections.confidence[valid_idx] if detections.confidence is not None else None,
                        class_id=detections.class_id[valid_idx] if detections.class_id is not None else None,
                        tracker_id=detections.tracker_id[valid_idx] if detections.tracker_id is not None else None
                    )
                    prev_pts = curr_pts[valid_idx].reshape(-1, 1, 2)
                else:
                    detections = sv.Detections.empty()
                    prev_pts = None
            
            prev_gray = gray.copy()
            pass

        tracked_objects = build_tracked_objects(detections, current_model.names)

        annotated_frame = frame.copy()

        fire_active = resolve_fire_frame(fire, power_save, tracked_objects, annotated_frame,
                                          frame_count, video_time, battery_low)

        if not fire_active:
            if len(detections) > 0 and detections.confidence is not None:
                labels = [
                    f"#{tracker_id} {model.names[class_id]} {confidence:0.2f}"
                    for class_id, tracker_id, confidence in zip(
                        detections.class_id, detections.tracker_id, detections.confidence
                    )
                ]
            else:
                labels = []

            if len(detections) > 0:
                annotated_frame = trace_annotator.annotate(scene=annotated_frame, detections=detections)
                annotated_frame = box_annotator.annotate(scene=annotated_frame, detections=detections)
                annotated_frame = label_annotator.annotate(
                    scene=annotated_frame, detections=detections, labels=labels
                )

        if fps_frame_count % FPS_WINDOW == 0:
            end_time = time.time()
            fps = FPS_WINDOW / (end_time - start_time)
            fps_frame_count = 0
            start_time = time.time()

        (text_width, text_height), _ = cv2.getTextSize(
            f"CPU FPS: {fps:.1f}", cv2.FONT_HERSHEY_SIMPLEX, 1, 2
        )

        fps_x_margin = annotated_frame.shape[1] - text_width - 20
        fps_y_margin = 40
        cv2.putText(
            annotated_frame, 
            f"CPU FPS: {fps:.1f}", 
            (fps_x_margin, fps_y_margin), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            1, 
            (0, 255, 0), 
            2
        )

        if frame_count == 1:
            new_clock_timer = time.monotonic()

        active_banners = []
        if last_telemetry_lines_battery:
            active_banners.append((last_telemetry_lines_battery, COLOR_WARNING))
        thermal_banner = thermal.banner_lines()
        if thermal_banner:
            active_banners.append((thermal_banner, thermal.banner_color()))
        if power_save.enabled:
            active_banners.append(
                ([f"POWER SAVE MODE ON (detect_interval={active_detect_interval})"], COLOR_WARNING)
            )
        draw_banners(annotated_frame, active_banners, origin=(10, 10))
        if annotated_frame is None:
            print("Помилка: annotated_frame не може бути None")
            stop_event.set()
            break

        cv2.imshow(WINDOW_NAME, annotated_frame)

        if thermal.pending_final_screenshot:
            thermal.save_final_screenshot(annotated_frame)

        key = cv2.waitKey(1) & 0xFF
        
        if key == ord("q"):
            stop_event.set()
            break
        if key == ord("f"):
            resolve_fire_activation(fire, power_save, tracked_objects, annotated_frame, frame_count, video_time)
        if key == ord("l"):
            power_save.toggle(frame, frame_count, video_time)     

    telemetry.stop()  
    stop_event.set()
    producer_thread.join()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()