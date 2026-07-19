import uvicorn
import json
from contextlib import asynccontextmanager
import aio_pika
from fastapi import FastAPI, HTTPException, status, Query
from pydantic import BaseModel
import redis.asyncio as aioredis
from asyncio import sleep
from datetime import datetime, timedelta, timezone
import asyncpg


class SystemMetrics(BaseModel):
    TS: str
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

DB_DSN = "postgres://iot_user:iot_password@iot_postgres:5432/iot_db"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global rabbitmq_connection, rabbitmq_channel, redis_client
    try:
        print("=== Connecting to Redis ===")
        redis_client = aioredis.from_url("redis://iot_redis:6379", decode_responses=True)
        await redis_client.ping()
        print("Redis is connected.")
    except Exception as e:
        print(f"Error, couldn't connect to Redis: {e}")
        raise e
    
    print("=== Connecting to RabbitMQ ===")
    while True:
        try:
            rabbitmq_connection = await aio_pika.connect_robust(
                "amqp://default:default@iot_rabbitmq:5672/"
            )
            rabbitmq_channel = await rabbitmq_connection.channel()

            await rabbitmq_channel.declare_exchange(
                name="metrics_exchange", 
                type=aio_pika.ExchangeType.FANOUT, 
                durable=True
            )
            print("=== Connection to RabbitMQ is successful. ===")
            break
        except Exception as e:
            print("Error, couldn't connect to RabbitMQ, retry in 5s...")
            await sleep(5)

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

@app.get("/api/v1/device/metrics/status")
async def get_current_status():
    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis is unavailable"
        )

    raw_data = await redis_client.get("device:my_pc")

    if not raw_data:
        return {"device": "my_pc", "status": "OFFLINE", "current_metrics": None}

    return {"device": "my_pc", "status": "ONLINE", "current_metrics": json.loads(raw_data)}

@app.get("/api/v1/device/metrics/history")
async def get_metrics_history_range(
    start: str = Query(..., description="Format: DD.MM.YYYY HH:MM"),
    end: str = Query(..., description="Format: DD.MM.YYYY HH:MM")
):
    date_format = "%d.%m.%Y %H:%M"
    msk_tz = timezone(timedelta(hours=3))

    try:
        try:
            start_dt = datetime.strptime(start, date_format).replace(tzinfo=msk_tz)
            end_dt = datetime.strptime(end, date_format).replace(tzinfo=msk_tz)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail="Incorrect data format. Use: DD.MM.YYYY HH:MM"
            )

        if start_dt > end_dt:
            raise HTTPException(status_code=400, detail="Start date can't be later than end date.")

        conn = await asyncpg.connect(DB_DSN)
        rows = await conn.fetch(
            """
            SELECT timestamp_msk, cpu, ram, uptime_hours, processes, battery_percent, disk_total_gb, disk_free_gb 
            FROM system_metrics 
            WHERE timestamp_msk BETWEEN $1 AND $2 
            ORDER BY id ASC
            """,
            start_dt,
            end_dt
        )
        await conn.close()

        history = [dict(row) for row in rows]
        return {
            "device": "my_pc",
            "start_requested": start,
            "end_requested": end,
            "records_count": len(history),
            "history": history
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading period from DB: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
