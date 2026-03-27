from fastapi import FastAPI
from src.db import get_status, get_machine_history, save_report

app = FastAPI()