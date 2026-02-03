import pika
import json
import os
import logging
import time

logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
QUEUE_NAME = "tasks"


def get_connection(max_retries=30, retry_delay=2):
    """Создает подключение к RabbitMQ с повторными попытками"""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        connection_attempts=max_retries,
        retry_delay=retry_delay
    )
    
    for attempt in range(max_retries):
        try:
            connection = pika.BlockingConnection(parameters)
            logger.info(f"Successfully connected to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT}")
            return connection
        except (pika.exceptions.AMQPConnectionError, ConnectionRefusedError, OSError) as e:
            if attempt < max_retries - 1:
                # Exponential backoff с максимумом 10 секунд
                delay = min(retry_delay * (2 ** min(attempt, 3)), 10)
                logger.warning(f"Failed to connect to RabbitMQ (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error(f"Failed to connect to RabbitMQ after {max_retries} attempts")
                raise


def publish_task(task_id: str, max_retries=5, retry_delay=1):
    """Публикует задачу в очередь с повторными попытками"""
    for attempt in range(max_retries):
        try:
            connection = get_connection(max_retries=3, retry_delay=1)
            channel = connection.channel()
            
            # Объявление очереди как durable для персистентности
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            
            # Публикация сообщения
            message = json.dumps({"task_id": str(task_id)})
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE_NAME,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                )
            )
            
            logger.info(f"Task {task_id} published to queue")
            connection.close()
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Failed to publish task {task_id} (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Failed to publish task {task_id} after {max_retries} attempts: {e}")
                return False
    return False


def consume_tasks(callback):
    """Слушает очередь и вызывает callback для каждой задачи"""
    connection = None
    channel = None
    
    try:
        logger.info(f"Attempting to connect to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT}...")
        connection = get_connection()
        channel = connection.channel()
        
        # Объявление очереди
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        
        # Настройка QoS для fair dispatch
        channel.basic_qos(prefetch_count=1)
        
        def on_message(ch, method, properties, body):
            try:
                message = json.loads(body)
                task_id = message.get("task_id")
                if task_id:
                    callback(task_id)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                else:
                    logger.error("Invalid message format")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        
        channel.basic_consume(
            queue=QUEUE_NAME,
            on_message_callback=on_message
        )
        
        logger.info("Waiting for messages. To exit press CTRL+C")
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("Stopping consumer")
        if channel:
            channel.stop_consuming()
        if connection and not connection.is_closed:
            connection.close()
    except Exception as e:
        logger.error(f"Error in consumer: {e}")
        if connection and not connection.is_closed:
            connection.close()
        raise
