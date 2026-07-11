import subprocess
import json
import asyncio
import time
import httpx
from datetime import datetime, timedelta, timezone

FASTAPI_URL = "http://localhost:8000/api/v1/metrics"
SEND_INTERVAL_SECONDS = 10

def get_system_metrics():
    """returns system metrics in json format"""
    try:
        power_shell_cmd = (
            'powershell -Command "'
            '$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; '
            '$os = Get-CimInstance Win32_OperatingSystem; '
            '$totalRam = $os.TotalVisibleMemorySize; '
            '$freeRam = $os.FreePhysicalMemory; '
            '$ramUsage = [Math]::Round((($totalRam - $freeRam) / $totalRam) * 100, 1); '
            '$uptime = [Math]::Round(((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours, 2); '
            '$disk = Get-CimInstance Win32_LogicalDisk -Filter \\"DeviceID=\'C:\'\\"; '
            '$diskTotal = [Math]::Round($disk.Size / 1GB, 1); '
            '$diskFree = [Math]::Round($disk.FreeSpace / 1GB, 1); '
            '$procCount = (Get-Process).Count; '
            '$battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue; '
            '$batPercent = if ($battery) { $battery.EstimatedChargeRemaining } else { -1 }; '
            
            '[PSCustomObject]@{Uptime_Hours=$uptime; CPU=$cpu; RAM=$ramUsage; Processes=$procCount;'
            'Battery_Percent=$batPercent; Disk_Total_GB=$diskTotal; Disk_Free_GB=$diskFree;} | ConvertTo-Json"'
        )
        
        output = subprocess.check_output(power_shell_cmd, shell=True, text=True, encoding='utf-8')

        data = json.loads(output)
        msk_tz = timezone(timedelta(hours=3))
        timestamp_msk = datetime.now(msk_tz).isoformat(timespec="seconds")
        data.update({'TS': timestamp_msk})
        
        return data
        
    except subprocess.CalledProcessError as e:
        print(f"System call error: {e}")
    except Exception as e:
        print(f"Error occured: {e}")

async def send_metrics_worker():
    print("=== Worker started ===")

    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            start_time = time.monotonic()
            try:
                metrics = get_system_metrics()
                print(f"[{time.strftime('%X')}] Sending metrics...")
                print(metrics)

                response = await client.post(FASTAPI_URL, json=metrics)

                if response.status_code in (200, 202):
                    print(f"Successful. Response: {response.json()}")
                else:
                    print(f"Error, code: {response.status_code}, Text: {response.text}")

            except httpx.RequestError as e:
                print(f"Network error! No connection to FastAPI. Retry in {SEND_INTERVAL_SECONDS} sec.")

            elapsed_time = time.monotonic() - start_time
            sleep_time = max(0.1, SEND_INTERVAL_SECONDS - elapsed_time)

            await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    try:
        asyncio.run(send_metrics_worker())
    except KeyboardInterrupt:
        print("=== Worker stopped ===")
