import cv2
import base64
import numpy as np
import time
import threading
from io import BytesIO
from PIL import Image

class DoorDetector:
    def __init__(self, threshold=30, min_area_percent=5, calibration_frames=10):
        """
        Инициализация детектора состояния двери.
        
        Args:
            threshold: Пороговое значение для бинаризации разницы между кадрами
            min_area_percent: Минимальный процент площади изменений для определения открытия/закрытия двери
            calibration_frames: Количество кадров для калибровки (усреднения)
        """
        self.threshold = threshold
        self.min_area_percent = min_area_percent
        self.calibration_frames = calibration_frames
        self.reference_frame = None
        self.door_state = "unknown"  # Начальное состояние: unknown, open, closed
        self.last_state_change = time.time()
        self.state_change_cooldown = 1.0  # Минимальное время между изменениями состояния (секунды)
        self.lock = threading.Lock()
        
    def calibrate(self, frames):
        """
        Калибровка детектора путем создания эталонного кадра (закрытая дверь).
        
        Args:
            frames: Список кадров для калибровки
        
        Returns:
            bool: True если калибровка успешна, False в противном случае
        """
        if not frames:
            return False
        
        with self.lock:
            # Преобразование кадров в оттенки серого и применение размытия
            gray_frames = []
            for frame in frames:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)
                gray_frames.append(gray)
            
            # Усреднение кадров для создания эталонного
            self.reference_frame = np.mean(gray_frames, axis=0).astype(np.uint8)
            self.door_state = "closed"  # После калибровки считаем, что дверь закрыта
            
        return True
    
    def detect_door_state(self, frame):
        """
        Определение состояния двери на основе сравнения с эталонным кадром.
        
        Args:
            frame: Текущий кадр с камеры
        
        Returns:
            str: Состояние двери ("open", "closed" или "unknown")
            frame: Кадр с визуализацией
        """
        with self.lock:
            if self.reference_frame is None:
                return "unknown", frame
            
            # Преобразование текущего кадра
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            # Вычисление абсолютной разницы между текущим и эталонным кадрами
            frame_delta = cv2.absdiff(self.reference_frame, gray)
            thresh = cv2.threshold(frame_delta, self.threshold, 255, cv2.THRESH_BINARY)[1]
            
            # Расширение порогового изображения для заполнения отверстий, затем поиск контуров
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Вычисление общей площади изменений
            total_area = 0
            for contour in contours:
                total_area += cv2.contourArea(contour)
            
            # Вычисление процента изменений относительно общей площади кадра
            frame_area = frame.shape[0] * frame.shape[1]
            change_percent = (total_area / frame_area) * 100
            
            # Определение состояния двери на основе процента изменений
            current_time = time.time()
            if change_percent > self.min_area_percent:
                new_state = "open"
            else:
                new_state = "closed"
            
            # Проверка времени с последнего изменения состояния для предотвращения частых переключений
            if new_state != self.door_state and (current_time - self.last_state_change) > self.state_change_cooldown:
                self.door_state = new_state
                self.last_state_change = current_time
            
            # Визуализация для отладки
            debug_frame = frame.copy()
            cv2.putText(debug_frame, f"Door: {self.door_state}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(debug_frame, f"Change: {change_percent:.2f}%", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # Отрисовка контуров изменений
            for contour in contours:
                if cv2.contourArea(contour) > 100:  # Игнорирование маленьких контуров
                    (x, y, w, h) = cv2.boundingRect(contour)
                    cv2.rectangle(debug_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            return self.door_state, debug_frame
    
    def update_settings(self, threshold=None, min_area_percent=None):
        """
        Обновление настроек детектора.
        
        Args:
            threshold: Новое пороговое значение
            min_area_percent: Новый минимальный процент площади изменений
        """
        with self.lock:
            if threshold is not None:
                self.threshold = threshold
            if min_area_percent is not None:
                self.min_area_percent = min_area_percent
        
        return True
    
    def get_settings(self):
        """
        Получение текущих настроек детектора.
        
        Returns:
            dict: Словарь с текущими настройками
        """
        with self.lock:
            return {
                "threshold": self.threshold,
                "min_area_percent": self.min_area_percent
            }
    
    def get_state(self):
        """
        Получение текущего состояния двери.
        
        Returns:
            str: Текущее состояние двери
        """
        with self.lock:
            return self.door_state
