import time
import uuid
import random
import logging
from sqlalchemy.orm import Session
from app import database, models, queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_task(task_id: str):
    """Обрабатывает задачу"""
    db: Session = database.SessionLocal()
    task = None
    try:
        task_uuid = uuid.UUID(task_id)
        task = db.query(models.Task).filter(models.Task.id == task_uuid).first()
        
        if not task:
            logger.error(f"Task {task_id} not found")
            return
        
        # Обновление статуса на processing
        task.status = models.TaskStatus.PROCESSING
        db.commit()
        logger.info(f"Task {task_id} status updated to processing")
        
        # Имитация обработки
        processing_time = random.uniform(2, 5)
        logger.info(f"Processing task {task_id} for {processing_time:.2f} seconds...")
        time.sleep(processing_time)
        
        # Имитация успешной или неудачной обработки
        if random.random() < 0.9: # Успех 90%
            task.status = models.TaskStatus.DONE
            task.result = f"Task processed successfully in {processing_time:.2f} seconds"
            logger.info(f"Task {task_id} completed successfully")
        else:
            task.status = models.TaskStatus.FAILED
            task.result = "Task processing failed (simulated error)"
            logger.warning(f"Task {task_id} failed")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {e}")
        # Помечение задачи как failed при ошибке
        try:
            if task is None:
                task_uuid = uuid.UUID(task_id)
                task = db.query(models.Task).filter(models.Task.id == task_uuid).first()
            if task:
                task.status = models.TaskStatus.FAILED
                task.result = f"Error: {str(e)}"
                db.commit()
        except Exception as update_error:
            logger.error(f"Failed to update task status: {update_error}")
            db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting worker...")
    # Инициализация БД при старте воркера
    database.init_db()
    # Задержка для полной инициализации RabbitMQ
    # (healthcheck может пройти раньше, чем порт будет готов)
    logger.info("Waiting for RabbitMQ to be fully ready...")
    time.sleep(5)
    queue.consume_tasks(process_task)
