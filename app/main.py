from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app import database, models, schemas, queue
import logging
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Task Queue Service", version="1.0.0")

# Инициализация БД
@app.on_event("startup")
async def startup_event():
    database.init_db()
    logger.info("Database initialized")


@app.post("/tasks", response_model=schemas.TaskResponse, status_code=201)
def create_task(task: schemas.TaskCreate, db: Session = Depends(database.get_db)):
    """Создает новую задачу и отправляет её в очередь на обработку"""
    try:
        # Создание задачи в БД
        db_task = models.Task(
            payload=task.payload,
            status=models.TaskStatus.PENDING
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        
        # Публикуем задачу в очередь
        if not queue.publish_task(db_task.id):
            logger.warning(f"Failed to publish task {db_task.id} to queue")
        
        return db_task
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create task")


@app.get("/tasks/{task_id}", response_model=schemas.TaskResponse)
def get_task(task_id: str, db: Session = Depends(database.get_db)):
    """Получает информацию о задаче по ID"""
    try:
        task = db.query(models.Task).filter(models.Task.id == uuid.UUID(task_id)).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    except Exception as e:
        logger.error(f"Error getting task: {e}")
        raise HTTPException(status_code=500, detail="Failed to get task")


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}
