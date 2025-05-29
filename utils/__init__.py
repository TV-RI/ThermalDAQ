import json
from typing import Dict
import time
from tqdm import tqdm

def read_config(config_file: str = 'config.json') -> Dict:
    with open(config_file, 'r') as f:
        return json.load(f)

def hold_time(seconds: int) -> None:
    print(f"Holding for {seconds} seconds...")
    for i in tqdm(range(seconds), desc="Holding", unit="s"):
        time.sleep(0.999)
    