import asyncio
import json
import aio_pika
import asyncpg
from datetime import datetime

RABBITMQ_URL = "amqp://default:default@iot_rabbitmq:5672/"
EXCHANGE_NAME = "metrics_exchange"
QUEUE_NAME = "metrics_history_queue"
DB_DSN = "postgres://iot_user:iot_password@iot_postgres:5432/iot_db"


async def init_database():
    print("Checking PostgreSQL table")
    conn = await asyncpg.connect(DB_DSN)
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS system_metrics (
                id SERIAL PRIMARY KEY,
                timestamp_msk TIMESTAMPTZ NOT NULL,
                uptime_hours REAL,
                cpu INT,
                ram REAL,
                processes INT,
                battery_percent INT,
                disk_total_gb REAL,
                disk_free_gb REAL
            );
        """
        )
        print("PostgreSQL table is created")
    finally:
        await conn.close()


async def process_message(message: aio_pika.abc.AbstractIncomingMessage):
    global db_connection

    async with message.process():
        try:
            metrics = json.loads(message.body.decode("utf-8"))
            raw_timestamp = metrics.get("TS")
            parsed_datetime = datetime.fromisoformat(raw_timestamp)

            if db_connection is None or db_connection.is_closed():
                print("Lost connection to PostgreSQL. Reconnecting...")
                db_connection = await asyncpg.connect(DB_DSN)

            await db_connection.execute(
                """
                INSERT INTO system_metrics 
                (timestamp_msk, uptime_hours, cpu, ram, processes, battery_percent, disk_total_gb, disk_free_gb)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                parsed_datetime,
                metrics.get("Uptime_Hours"),
                metrics.get("CPU"),
                metrics.get("RAM"),
                metrics.get("Processes"),
                metrics.get("Battery_Percent"),
                metrics.get("Disk_Total_GB"),
                metrics.get("Disk_Free_GB"),
            )
            print(f"Metrics at {raw_timestamp} is stored")

        except Exception as e:
            print(f"PostgreSQL data insert error: {e}")


async def main():
    global db_connection
    print("=== Starting DB Worker ===")

    while True:
        try:
            await init_database()
            break
        except Exception:
            print("Couldn't connect to PostgreSQL. Retry in 5s...")
            await asyncio.sleep(5)

    print("Openning continuous connection to PostgreSQL...")
    while True:
        try:
            db_connection = await asyncpg.connect(DB_DSN)
            print("Connection to PostreSQL is established!")
            break
        except Exception:
            print("Couldn't establish connection to PostgreSQL. Retry in 5s...")
            await asyncio.sleep(5)

    rabbitmq_connection = None
    print("Connecting to RabbitMQ...")
    while True:
        try:
            rabbitmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
            break
        except Exception:
            print("Couldn't connect to RabbitMQ. Retry in 5s...")
            await asyncio.sleep(5)

    channel = await rabbitmq_connection.channel()
    exchange = await channel.declare_exchange(
        name=EXCHANGE_NAME, type=aio_pika.ExchangeType.FANOUT, durable=True
    )
    queue = await channel.declare_queue(name=QUEUE_NAME, durable=True)
    await queue.bind(exchange=exchange, routing_key="")

    print(f"=== Queue '{QUEUE_NAME}' is ready. Waiting for data... ===")
    await queue.consume(process_message)

    try:
        await asyncio.Future()
    finally:
        print("=== Closing the connection to PostgreSQL... ===")
        if db_connection and not db_connection.is_closed():
            await db_connection.close()
        if rabbitmq_connection:
            await rabbitmq_connection.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n=== DB Worker stopped ===")
