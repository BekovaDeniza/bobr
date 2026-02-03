# Task Queue Service

Backend-сервис на FastAPI для асинхронной обработки задач через очередь сообщений.

### Запуск

```bash
docker-compose up --build
```

### Локальный запуск без Docker

1. Создайте виртуальное окружение:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Запустите PostgreSQL и RabbitMQ (через Docker или локально)

4. Установите переменные окружения:
```bash
# Windows (PowerShell)
$env:DATABASE_URL="postgresql://postgres:postgres@localhost:5432/taskdb"
$env:RABBITMQ_HOST="localhost"
$env:RABBITMQ_PORT="5672"

# Linux/Mac
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/taskdb"
export RABBITMQ_HOST="localhost"
export RABBITMQ_PORT="5672"
```

5. Запустите сервер:
```bash
uvicorn app.main:app --reload
```

6. Запустите воркер (в отдельном терминале):
```bash
python app/worker.py
```


Сервис будет доступен по адресу: http://localhost:8000

RabbitMQ Management UI: http://localhost:15672 (guest/guest)

### Использование API

#### Создание задачи

```bash
curl -X POST "http://localhost:8000/tasks" \
  -H "Content-Type: application/json" \
  -d '{"payload": "test task"}'
```

Ответ:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": "test task",
  "status": "pending",
  "result": null,
  "created_at": "2026-02-03T01:13:28.345428Z",
  "updated_at": "2026-02-03T01:13:28.345428Z"
}
```

#### Получение статуса задачи

```bash
curl "http://localhost:8000/tasks/{task_id}"
```

#### Health check

```bash
curl "http://localhost:8000/health"
```

## Обоснование выбора RabbitMQ

1. **Простота использования**: RabbitMQ проще настроить и использовать для простых очередей. Kafka требует больше конфигурации и лучше подходит для больших объемов данных.

2. **Механизм подтверждений**: RabbitMQ имеет встроенный механизм ack/nack, который идеально подходит для гарантированной доставки задач.

3. **Overhead**: Для небольшого сервиса RabbitMQ имеет меньший overhead по сравнению с Kafka.

4. **Масштабирование воркеров**: RabbitMQ позволяет легко масштабировать количество воркеров - достаточно запустить больше контейнеров worker, и они автоматически будут распределять задачи между собой.

5. **Управление**: RabbitMQ Management UI предоставляет удобный интерфейс для мониторинга очередей, сообщений и производительности.

## Масштабирование решения

### Горизонтальное масштабирование

1. **Воркеры**: Можно запустить несколько экземпляров worker для параллельной обработки задач:
   ```yaml
   worker:
     deploy:
       replicas: 5
   ```

2. **API серверы**: Можно запустить несколько экземпляров backend за load balancer (nginx/traefik):
   ```yaml
   backend:
     deploy:
       replicas: 3
   ```

3. **База данных**: 
   - Использовать connection pooling (уже реализовано через SQLAlchemy)
   - При необходимости: read replicas для чтения, master для записи
   - Шардирование по task_id при очень больших объемах

4. **RabbitMQ**:
   - RabbitMQ кластер для высокой доступности
   - Mirrored queues для репликации сообщений между нодами
   - Использование RabbitMQ Federation для распределения нагрузки

### Вертикальное масштабирование

- Увеличение ресурсов (CPU, RAM) для каждого компонента
- Настройка connection pools и worker threads

### Оптимизации

- Использование Redis для кеширования часто запрашиваемых задач
- Batch processing для группировки похожих задач
- Приоритетные очереди для важных задач

## Точки отказа и решения

### 1. RabbitMQ недоступен
**Проблема**: Если RabbitMQ падает, новые задачи не могут быть отправлены в очередь.

### 2. PostgreSQL недоступен
**Проблема**: При недоступности БД невозможно сохранить или обновить задачи.

### 3. Воркер падает во время обработки
**Проблема**: Задача остается в статусе processing и не обрабатывается.

### 4. Потеря сообщений
**Проблема**: Сообщения могут быть потеряны при сбоях.

### 5. Дублирование задач
**Проблема**: При retry могут создаваться дубликаты задач.


## Улучшения для продакшена

### Безопасность

1. **Аутентификация и авторизация**:
   - JWT токены для API
   - RBAC для управления доступом
   - API keys для внешних интеграций

2. **Защита данных**:
   - Шифрование чувствительных данных в payload
   - HTTPS для всех соединений
   - Secrets management (Vault, AWS Secrets Manager)

3. **Валидация**:
   - Более строгая валидация payload
   - Rate limiting для предотвращения злоупотреблений
   - Input sanitization

### Мониторинг и логирование

1. **Логирование**:
   - Structured logging (JSON формат)
   - Централизованное логирование (ELK stack, Loki)
   - Log levels и ротация логов
   - Correlation IDs для трейсинга запросов

2. **Метрики**:
   - Prometheus для сбора метрик
   - Grafana для визуализации
   - Метрики: количество задач, время обработки, ошибки, размер очереди

3. **Трейсинг**:
   - OpenTelemetry для distributed tracing
   - Отслеживание полного пути задачи от создания до завершения

### Надежность

1. **Обработка ошибок**:
   - Более детальная обработка различных типов ошибок
   - Retry policies с exponential backoff
   - Circuit breakers для внешних зависимостей

2. **Резервное копирование**:
   - Автоматические бэкапы БД
   - Репликация данных
   - Disaster recovery план

3. **Тестирование**:
   - Unit тесты для бизнес-логики
   - Integration тесты для API
   - E2E тесты для полного flow
   - Load testing для проверки производительности

### Производительность

1. **Оптимизация БД**:
   - Индексы на часто запрашиваемые поля (status, created_at)
   - Партиционирование таблиц по датам
   - Query optimization

2. **Кеширование**:
   - Redis для кеширования статусов задач
   - Кеширование метаданных

3. **Асинхронность**:
   - Использование async/await в FastAPI для лучшей производительности
   - Async database drivers

### Операционные улучшения

1. **CI/CD**:
   - Автоматические тесты в pipeline
   - Автоматический деплой при изменениях
   - Blue-green или canary deployments

2. **Конфигурация**:
   - Environment-specific конфигурации
   - Feature flags для постепенного rollout
   - Конфигурация через переменные окружения или config files

3. **Документация**:
   - OpenAPI/Swagger документация (уже доступна по /docs)
   - API версионирование
   - Документация по архитектуре и deployment

### Дополнительные функции

1. **Приоритеты задач**: Поддержка приоритетных очередей
2. **Scheduled tasks**: Отложенное выполнение задач
3. **Task dependencies**: Зависимости между задачами
4. **Webhooks**: Уведомления о завершении задач
