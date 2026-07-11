import asyncio
import json
import aio_pika

RABBITMQ_URL = "amqp://default:default@127.0.0.1:5672/"
EXCHANGE_NAME = "metrics_exchange"
QUEUE_NAME = "metrics_alerts_queue"

CPU_THRESHOLD_PERCENT = 5
RAM_THRESHOLD_PERCENT = 30
BATTERY_THRESHOLD_PERCENT = 30
DISK_THRESHOLD_PERCENT = 15


async def process_message(message: aio_pika.abc.AbstractIncomingMessage):
    async with message.process():
        try:
            metrics = json.loads(message.body.decode("utf-8"))
            ts = metrics.get("TS", 0)
            cpu = metrics.get("CPU", 0)
            ram = metrics.get("RAM", 0)
            battery = metrics.get("Battery_Percent", 0)
            disk_total = metrics.get("Disk_Total_GB", 0)
            disk_free = metrics.get("Disk_Free_GB", 0)
            disk_percent = disk_free / disk_total * 100

            print(f"\n{ts}")

            if cpu > CPU_THRESHOLD_PERCENT:
                print(f"Warning: High CPU Usage! Current: {cpu}%")
                # TODO: tg_bot.send_message(...)

            if ram > RAM_THRESHOLD_PERCENT:
                print(f"Critical: Running out of RAM! Current: {ram}%")

            if battery != -1 and battery < BATTERY_THRESHOLD_PERCENT:
                print(f"Critical: Almost out of battery! Current: {battery}%")

            if disk_percent < DISK_THRESHOLD_PERCENT:
                print(f"Warning: Running out of space! Current: {disk_free} GB")

        except Exception as e:
            print(f"Error with the message: {e}")


async def main():
    print("=== Starting the alert sender... ===")
    
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()

    exchange = await channel.declare_exchange(
        name=EXCHANGE_NAME,
        type=aio_pika.ExchangeType.FANOUT,
        durable=True
    )

    queue = await channel.declare_queue(name=QUEUE_NAME, durable=True)

    await queue.bind(exchange=exchange, routing_key="")

    print(f"=== Queue '{QUEUE_NAME}' Succesfully binded to the exchange. Waiting for the metrics... ===")

    await queue.consume(process_message)

    try:
        await asyncio.Future()
    finally:
        await connection.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n=== Alert sender stopped ===")
