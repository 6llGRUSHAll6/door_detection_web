// Основной JavaScript файл для управления веб-интерфейсом
document.addEventListener('DOMContentLoaded', function() {
    // Элементы интерфейса
    const videoFeed = document.getElementById('video-feed');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const calibrateBtn = document.getElementById('calibrate-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const settingsPanel = document.getElementById('settings-panel');
    const thresholdSlider = document.getElementById('threshold');
    const thresholdValue = document.getElementById('threshold-value');
    const minAreaSlider = document.getElementById('min-area');
    const minAreaValue = document.getElementById('min-area-value');
    const saveSettingsBtn = document.getElementById('save-settings');
    const logContainer = document.getElementById('log-container');
    const calibrateLoading = document.getElementById('calibrate-loading');

    // Настройка WebSocket соединения
    const socket = io();
    let isConnected = false;

    // Обработка событий соединения
    socket.on('connect', function() {
        isConnected = true;
        addLogEntry('Соединение с сервером установлено');
    });

    socket.on('disconnect', function() {
        isConnected = false;
        addLogEntry('Соединение с сервером потеряно', true);
        videoFeed.innerHTML = '<p>Соединение потеряно. Пытаемся восстановить...</p>';
    });

    // Обработка видеопотока
    socket.on('video_feed', function(data) {
        if (data.image) {
            // Если в видеофиде уже есть изображение, обновляем его src
            let img = videoFeed.querySelector('img');
            if (!img) {
                // Если изображения нет, создаем новый элемент
                videoFeed.innerHTML = '';
                img = document.createElement('img');
                videoFeed.appendChild(img);
            }
            img.src = 'data:image/jpeg;base64,' + data.image;
        }
    });

    // Обработка статуса двери
    socket.on('door_status', function(data) {
        updateDoorStatus(data.status);
        addLogEntry(`Статус двери: ${data.status}`);
    });

    // Обработка ошибок
    socket.on('error_message', function(data) {
        addLogEntry(data.message, true);
        if (data.type === 'camera_error') {
            videoFeed.innerHTML = '<p class="error-message">Ошибка доступа к камере. Проверьте подключение.</p>';
        }
    });

    // Функция обновления статуса двери
    function updateDoorStatus(status) {
        statusDot.className = 'status-dot';
        
        if (status === 'open') {
            statusDot.classList.add('open');
            statusText.textContent = 'Статус: Дверь открыта';
        } else if (status === 'closed') {
            statusDot.classList.add('closed');
            statusText.textContent = 'Статус: Дверь закрыта';
        } else {
            statusText.textContent = 'Статус: Определение...';
        }
    }

    // Функция добавления записи в журнал
    function addLogEntry(message, isError = false) {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        if (isError) {
            entry.style.color = 'var(--danger-color)';
        }
        
        const timestamp = new Date().toLocaleTimeString();
        entry.textContent = `[${timestamp}] ${message}`;
        
        logContainer.appendChild(entry);
        logContainer.scrollTop = logContainer.scrollHeight;
        
        // Ограничение количества записей в журнале
        while (logContainer.children.length > 100) {
            logContainer.removeChild(logContainer.firstChild);
        }
    }

    // Обработчики событий для кнопок
    calibrateBtn.addEventListener('click', function() {
        if (!isConnected) {
            addLogEntry('Нет соединения с сервером', true);
            return;
        }
        
        calibrateBtn.disabled = true;
        calibrateLoading.classList.remove('hidden');
        
        socket.emit('calibrate');
        addLogEntry('Запущена калибровка...');
        
        // Восстановление кнопки через 5 секунд
        setTimeout(function() {
            calibrateBtn.disabled = false;
            calibrateLoading.classList.add('hidden');
        }, 5000);
    });

    settingsBtn.addEventListener('click', function() {
        settingsPanel.classList.toggle('active');
    });

    // Обновление значений слайдеров
    thresholdSlider.addEventListener('input', function() {
        thresholdValue.textContent = this.value;
    });

    minAreaSlider.addEventListener('input', function() {
        minAreaValue.textContent = this.value + '%';
    });

    // Сохранение настроек
    saveSettingsBtn.addEventListener('click', function() {
        if (!isConnected) {
            addLogEntry('Нет соединения с сервером', true);
            return;
        }
        
        const settings = {
            threshold: parseInt(thresholdSlider.value),
            min_area_percent: parseInt(minAreaSlider.value)
        };
        
        socket.emit('update_settings', settings);
        addLogEntry('Настройки сохранены');
        settingsPanel.classList.remove('active');
    });

    // Инициализация
    addLogEntry('Веб-интерфейс инициализирован');
});
