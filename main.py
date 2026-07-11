from fastapi import FastAPI
from monitoring import get_system_metrics

app = FastAPI()


@app.get("/")
async def root():
    return get_system_metrics()