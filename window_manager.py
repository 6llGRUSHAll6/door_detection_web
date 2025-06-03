import pygetwindow as gw
import time
import threading

class WindowManager:
    def __init__(self):
        """
        Инициализация менеджера окон.
        """
        self.minimized_windows = []
        self.lock = threading.Lock()
        
    def minimize_all_windows(self):
        """
        Сворачивает все активные окна и сохраняет их список.
        
        Returns:
            int: Количество свернутых окон
        """
        with self.lock:
            # Очистка предыдущего списка свернутых окон
            self.minimized_windows = []
            
            # Получение всех видимых окон
            all_windows = gw.getAllWindows()
            minimized_count = 0
            
            for window in all_windows:
                # Проверка, что окно видимо и не свернуто
                if window.isMinimized == False and window.visible:
                    try:
                        # Сохраняем информацию об окне перед сворачиванием
                        self.minimized_windows.append({
                            'title': window.title,
                            'window': window
                        })
                        # Сворачиваем окно
                        window.minimize()
                        minimized_count += 1
                        # Небольшая задержка для стабильности
                        time.sleep(0.1)
                    except Exception as e:
                        print(f"Ошибка при сворачивании окна '{window.title}': {e}")
            
            return minimized_count
    
    def restore_all_windows(self):
        """
        Восстанавливает все ранее свернутые окна.
        
        Returns:
            int: Количество восстановленных окон
        """
        with self.lock:
            restored_count = 0
            
            # Восстановление окон в обратном порядке (чтобы сохранить z-order)
            for window_info in reversed(self.minimized_windows):
                try:
                    window = window_info['window']
                    # Проверка, существует ли еще окно
                    if window.title:  # Если окно все еще существует
                        window.restore()
                        restored_count += 1
                        # Небольшая задержка для стабильности
                        time.sleep(0.1)
                except Exception as e:
                    print(f"Ошибка при восстановлении окна '{window_info['title']}': {e}")
            
            # Очистка списка после восстановления
            self.minimized_windows = []
            return restored_count
    
    def get_minimized_windows_count(self):
        """
        Возвращает количество сохраненных свернутых окон.
        
        Returns:
            int: Количество свернутых окон
        """
        with self.lock:
            return len(self.minimized_windows)
            
    def get_window_status(self):
        """
        Возвращает информацию о текущем состоянии окон.
        
        Returns:
            dict: Информация о состоянии окон
        """
        with self.lock:
            all_windows = gw.getAllWindows()
            visible_count = 0
            minimized_count = 0
            
            for window in all_windows:
                if window.visible:
                    if window.isMinimized:
                        minimized_count += 1
                    else:
                        visible_count += 1
            
            return {
                "visible_windows": visible_count,
                "minimized_windows": minimized_count,
                "saved_minimized_windows": len(self.minimized_windows)
            }
