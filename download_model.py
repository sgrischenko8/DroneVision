import os
import shutil
from ultralytics import YOLO

def export_to_openvino():
    print("Завантаження моделі YOLOv8n...")
    model = YOLO("yolov8n.pt")
    model.export(format="openvino", imgsz=480, half=True, device="cpu")
    
    if os.path.exists("yolov8n_480_openvino_model"):
        shutil.rmtree("yolov8n_480_openvino_model") # видаляємо стару, якщо була.   
    shutil.move("yolov8n_openvino_model", "yolov8n_480_openvino_model")
    
    # --- 2. Експорт легкої моделі (320x320) ---
    print("Експорт легкої моделі (320x320)...")
    model.export(format="openvino", imgsz=320, half=True, device="cpu")
    
    if os.path.exists("yolov8n_320_openvino_model"):
        shutil.rmtree("yolov8n_320_openvino_model") # Потрібно щоб більша модель не перезаписувалась легшою
    shutil.move("yolov8n_openvino_model", "yolov8n_320_openvino_model")
    
if __name__ == "__main__":
    export_to_openvino()