import asyncio
import os
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FASTAPI_BASE_URL = "http://iot_fastapi:8000/api/v1"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class HistoryStates(StatesGroup):
    waiting_for_range = State()


def get_reply_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Check current status")],
            [KeyboardButton(text="Metrics history request")]
        ],
        resize_keyboard=True,
        input_field_placeholder="What do you want to do?"
    )
    return keyboard


async def get_status_msg() -> str:
    async with httpx.AsyncClient(timeout=4.0) as client:
        try:
            response = await client.get(f"{FASTAPI_BASE_URL}/device/metrics/status")
            if response.status_code != 200:
                return f"API server error: Code {response.status_code}"
            
            data = response.json()
            metrics = data.get("current_metrics")

            if data.get("status") == "OFFLINE" or not metrics:
                return "Current status: OFFLINE\n\nDidn't recieve any data in last 30s."

            return (
                f"Current status: ONLINE**\n\n"
                f"Time(Moscow): `{metrics.get('TS')}`\n"
                f"CPU Usage: `{metrics.get('CPU')}%`\n"
                f"RAM Usage: `{metrics.get('RAM')}%`\n"
                f"Battery: `{metrics.get('Battery_Percent')}%`\n"
                f"Disk Total: `{metrics.get('Disk_Total_GB')} GB`\n"
                f"Disk Free: `{metrics.get('Disk_Free_GB')} GB`\n"
                f"Processes: `{metrics.get('Processes')}`"
            )
        except Exception as e:
            return f"No connection to FastAPI server: {e}"


async def get_history_by_range(start_str: str, end_str: str) -> str:
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            params = {"start": start_str, "end": end_str}
            response = await client.get(f"{FASTAPI_BASE_URL}/device/metrics/history", params=params)

            if response.status_code == 400:
                return f"{response.json().get('detail')}"
            elif response.status_code != 200:
                return f"API Error: Code {response.status_code}"

            data = response.json()
            history_list = data.get("history", [])

            if not history_list:
                return f"For period `{start_str}` to `{end_str}` no data was found."

            msg = f"Metrics for {start_str} to {end_str} ({len(history_list)} records.):**\n\n"
            
            for i, record in enumerate(history_list[:15], 1):
                time_raw = record.get('timestamp_msk', '')
                time_clean = time_raw.replace('T', ' ').split('+')[0].split('.')[0]
                ram_rounded = round(record.get('ram', 0), 1)
                disk_free = round(record.get('disk_free_gb', 0), 1)
                cpu = record.get('cpu', 0)
                processes = record.get('processes', 0)
                battery = record.get('battery_percent', -1)
                bat_str = f"{battery}%" if battery != -1 else "Plugged in"
                uptime = record.get("uptime_hours", 0)

                msg += (
                    f"{i}. `{time_clean}` | Uptime: {uptime} hrs\n"
                    f"    CPU: `{cpu}%` | RAM: `{ram_rounded}%` | Processes: `{processes}`\n"
                    f"    Free space: `{disk_free} GB` | Battery: `{bat_str}`\n"
                    f"    ----------------------------------------\n"
                )

            if len(history_list) > 15:
                msg += f"\nFirst 15 records are displayed out of {len(history_list)}*"
            return msg
        except Exception as e:
            return f"No connection to FastAPI server: {e}"



@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Hi! I am IoT monitoring bot.", reply_markup=get_reply_keyboard())


@dp.message(lambda msg: msg.text == "Check current status" or msg.text == "/status")
async def handle_status(message: types.Message):
    text = await get_status_msg()
    await message.answer(text, parse_mode="Markdown")


@dp.message(lambda msg: msg.text == "Metrics history request" or msg.text == "/history")
async def handle_history_request(message: types.Message, state: FSMContext):
    await state.set_state(HistoryStates.waiting_for_range)
    await message.answer(
        "Enter time period\n\n"
        "Use this format:\n"
        "`DD.MM.YYYY HH:MM - DD.MM.YYYY HH:MM`\n\n"
        "Example:\n"
        "`19.07.2026 12:00 - 19.07.2026 12:30`"
    )


@dp.message(HistoryStates.waiting_for_range)
async def process_history_range(message: types.Message, state: FSMContext):
    raw_text = message.text.strip()

    try:
        start_part, end_part = raw_text.split("-")
        start_str = start_part.strip()
        end_str = end_part.strip()
    except ValueError:
        await message.answer("Wrong format. Try again. Use `-`\n\nExample: `19.07.2026 12:00 - 19.07.2026 12:30`")
        return

    waiting_msg = await message.answer("Searching for data...")
    result_text = await get_history_by_range(start_str, end_str)
    
    await waiting_msg.delete()
    await message.answer(
        result_text, 
        parse_mode="Markdown", 
        reply_markup=get_reply_keyboard()
    )
    
    await state.clear()


async def main():
    print("=== Telegram bot is working ===")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())