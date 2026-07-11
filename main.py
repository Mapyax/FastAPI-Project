import uvicorn
import json
from contextlib import asynccontextmanager
import aio_pika
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel


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

@asynccontextmanager
async def lifespan(app: FastAPI):
    global rabbitmq_connection, rabbitmq_channel
    print("=== Connecting to RabbitMQ ===")
    try:
        rabbitmq_connection = await aio_pika.connect_robust(
            "amqp://default:default@127.0.0.1:5672/"
        )
        rabbitmq_channel = await rabbitmq_connection.channel()

        await rabbitmq_channel.declare_exchange(
            name="metrics_exchange", 
            type=aio_pika.ExchangeType.FANOUT, 
            durable=True
        )
        print("=== Connection to RabbitMQ successful, created Exchange! ===")
    except Exception as e:
        print(f"Error, couldn't connect to RabbitMQ: {e}")
        raise e

    yield

    print("=== Closing connection to RabbitMQ... ===")
    if rabbitmq_connection:
        await rabbitmq_connection.close()
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
        print(f"Error occured while sending metrics to RabbitMQ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Couldn't send packet to the queue"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
