from fastapi import FastAPI, status
from pydantic import BaseModel
import uvicorn

app = FastAPI()


class SystemMetrics(BaseModel):
    Uptime_Hours: float | None
    CPU: int | None
    RAM: float | None
    Processes: int | None
    Battery_Percent: int | None
    Disk_Total_GB: float | None
    Disk_Free_GB: float | None

@app.post("/api/v1/metrics", status_code=status.HTTP_202_ACCEPTED)
async def receive_metrics(metrics: SystemMetrics):
    metrics_dict = metrics.model_dump()
    
    print("--- Recieved data ---")
    print(f"CPU Usage: {metrics_dict['CPU']}%")
    print(f"RAM Usage: {metrics_dict['RAM']}%")
    
    return {"status": "accepted"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)