import sys
import os
import cv2
import base64
import threading
import time
import json
from flask import Flask, render_template, Response, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
import numpy as np
from door_detector import DoorDetector
from window_manager import WindowManager

# Добавление пути для корректного импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Инициализация Flask приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = 'door_detection_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Глобальные переменные
camera = None
door_detector = None
window_manager = None
camera_thread = None
stop_camera_thread = False
door_was_opened = False
previous_state = "unknown"

def initialize_system():
    """
    Инициализация системы обнаружения двери и управления окнами
    """
    global door_detector, window_manager
    
    # Инициализация детектора двери
    door_detector = DoorDetector(threshold=30, min_area_percent=5, calibration_frames=10)
    
    # Инициализация менеджера окон
    window_manager = WindowManager()
    
    return True

def get_camera():
    """
    Получение доступа к камере
    """
    global camera
    
    if camera is not None and camera.isOpened():
        return camera
    
    # Попытка открыть камеру
    camera = cv2.VideoCapture(0)
    
    if not camera.isOpened():
        return None
    
    return camera

def release_camera():
    """
    Освобождение ресурсов камеры
    """
    global camera
    
    if camera is not None and camera.isOpened():
        camera.release()
        camera = None

def process_video_feed():
    """
    Обработка видеопотока и отправка кадров клиентам
    """
    global camera, door_detector, window_manager, stop_camera_thread, door_was_opened, previous_state
    
    # Получение доступа к камере
    cam = get_camera()
    if cam is None:
        socketio.emit('error_message', {'message': 'Не удалось получить доступ к камере', 'type': 'camera_error'})
        return
    
    # Основной цикл обработки видео
    while not stop_camera_thread:
        # Чтение кадра
        success, frame = cam.read()
        
        if not success:
            socketio.emit('error_message', {'message': 'Ошибка чтения кадра с камеры', 'type': 'camera_error'})
            time.sleep(1)  # Пауза перед следующей попыткой
            continue
        
        # Определение состояния двери
        if door_detector.reference_frame is not None:
            current_state, debug_frame = door_detector.detect_door_state(frame)
            
            # Если состояние изменилось
            if current_state != previous_state:
                socketio.emit('door_status', {'status': current_state})
                
                # Если дверь открылась
                if current_state == "open" and previous_state == "closed":
                    window_manager.minimize_all_windows()
                    door_was_opened = True
                
                # Если дверь закрылась после того, как была открыта
                elif current_state == "closed" and previous_state == "open" and door_was_opened:
                    window_manager.restore_all_windows()
                    door_was_opened = False
                
                previous_state = current_state
            
            # Преобразование кадра для отправки через WebSocket
            _, buffer = cv2.imencode('.jpg', debug_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            
            # Отправка кадра клиентам
            socketio.emit('video_feed', {'image': jpg_as_text})
        else:
            # Если еще не выполнена калибровка, отправляем исходный кадр
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            socketio.emit('video_feed', {'image': jpg_as_text})
        
        # Пауза для снижения нагрузки
        time.sleep(0.1)
    
    # Освобождение ресурсов
    release_camera()

def start_camera_thread():
    """
    Запуск потока обработки видео
    """
    global camera_thread, stop_camera_thread
    
    if camera_thread is None or not camera_thread.is_alive():
        stop_camera_thread = False
        camera_thread = threading.Thread(target=process_video_feed)
        camera_thread.daemon = True
        camera_thread.start()

def stop_camera_thread():
    """
    Остановка потока обработки видео
    """
    global stop_camera_thread
    stop_camera_thread = True

# Маршруты Flask
@app.route('/')
def index():
    """
    Главная страница
    """
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    """
    Обработка статических файлов
    """
    return send_from_directory('static', path)

# События SocketIO
@socketio.on('connect')
def handle_connect():
    """
    Обработка подключения клиента
    """
    # Запуск потока обработки видео при подключении первого клиента
    start_camera_thread()
    
    # Отправка текущих настроек
    if door_detector is not None:
        emit('settings', door_detector.get_settings())
    
    # Отправка текущего состояния двери
    if door_detector is not None and door_detector.reference_frame is not None:
        emit('door_status', {'status': door_detector.get_state()})
    else:
        emit('door_status', {'status': 'unknown'})

@socketio.on('disconnect')
def handle_disconnect():
    """
    Обработка отключения клиента
    """
    # Если нет активных клиентов, останавливаем поток обработки видео
    if len(socketio.server.eio.sockets) == 0:
        stop_camera_thread()

@socketio.on('calibrate')
def handle_calibrate():
    """
    Обработка запроса на калибровку
    """
    global door_detector
    
    # Получение доступа к камере
    cam = get_camera()
    if cam is None:
        emit('error_message', {'message': 'Не удалось получить доступ к камере для калибровки', 'type': 'camera_error'})
        return
    
    # Сбор кадров для калибровки
    frames = []
    for _ in range(door_detector.calibration_frames):
        success, frame = cam.read()
        if success:
            frames.append(frame)
        time.sleep(0.1)
    
    # Выполнение калибровки
    if frames:
        if door_detector.calibrate(frames):
            emit('calibration_complete', {'success': True})
            emit('door_status', {'status': 'closed'})
        else:
            emit('error_message', {'message': 'Ошибка калибровки', 'type': 'calibration_error'})
    else:
        emit('error_message', {'message': 'Не удалось получить кадры для калибровки', 'type': 'camera_error'})

@socketio.on('update_settings')
def handle_update_settings(data):
    """
    Обработка запроса на обновление настроек
    """
    global door_detector
    
    threshold = data.get('threshold')
    min_area_percent = data.get('min_area_percent')
    
    if door_detector.update_settings(threshold, min_area_percent):
        emit('settings_updated', {'success': True})
    else:
        emit('error_message', {'message': 'Ошибка обновления настроек', 'type': 'settings_error'})

# Инициализация системы при запуске
initialize_system()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
