import uvicorn
import json
from contextlib import asynccontextmanager
import aio_pika
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import redis.asyncio as aioredis


class SystemMetrics(BaseModel):
    Uptime_Hours: float | None
    CPU: int | None
    RAM: float | None
    Processes: int | None
    Battery_Percent: int | None
    Disk_Total_GB: float | None
    Disk_Free_GB: float | None

rabbitmq_connection: aio_pika.RobustConnection | None = None
rabbitmq_channel: aio_pika.RobustChannel | None = None
redis_client: aioredis.Redis | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global rabbitmq_connection, rabbitmq_channel, redis_client
    print("=== Connecting to RabbitMQ and Redis ===")
    try:
        redis_client = aioredis.from_url("redis://127.0.0.1:6379", decode_responses=True)
        await redis_client.ping()
        print("Redis is connected.")

        rabbitmq_connection = await aio_pika.connect_robust(
            "amqp://default:default@127.0.0.1:5672/"
        )
        rabbitmq_channel = await rabbitmq_connection.channel()

        await rabbitmq_channel.declare_exchange(
            name="metrics_exchange", 
            type=aio_pika.ExchangeType.FANOUT, 
            durable=True
        )
        print("=== Connection to RabbitMQ and Redis is successful. ===")
    except Exception as e:
        print(f"Error, couldn't connect to RabbitMQ or Redis: {e}")
        raise e

    yield

    print("=== Closing connections... ===")
    if rabbitmq_connection:
        await rabbitmq_connection.close()
    if redis_client:
        await redis_client.close()
    print("=== All connections closed === ")

app = FastAPI(lifespan=lifespan)


@app.post("/api/v1/metrics", status_code=status.HTTP_202_ACCEPTED)
async def receive_metrics(metrics: SystemMetrics):
    if not rabbitmq_channel:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Broker is unavailable"
        )
    
    try:
        metrics_dict = metrics.model_dump()
        message_body = json.dumps(metrics_dict).encode("utf-8")

        await redis_client.set("device:my_pc", message_body, ex=30)

        exchange = await rabbitmq_channel.get_exchange("metrics_exchange")

        await exchange.publish(
            aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=""
        )

        print("Metrics successfully sent to RabbitMQ Exchange")
        return {"status": "accepted"}

    except Exception as e:
        print(f"Error occured: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server error"
        )

@app.get("/api/v1/device/my_pc/status")
async def get_current_status():
    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis is unavailable"
        )

    raw_data = await redis_client.get("device:my_pc")

    if not raw_data:
        return {"device": "my_pc", "status": "OFFLINE", "current_metrics": None}

    return {"device": "my_pc", "status": "ONLINE", "current_metrics": json.loads(raw_data)}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
