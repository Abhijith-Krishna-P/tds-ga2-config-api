import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent
ENVIRONMENT = os.getenv("APP_ENV", "development")

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI()

# Allow the assignment page to call this API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def normalize_key(key):
    key = key.strip().lower()
    if key.startswith("app_"):
        key = key[4:]
    if key == "num_workers":
        key = "workers"
    return key


def coerce(key, value):
    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "on")

    if isinstance(value, bool):
        return value

    return str(value)


def effective_config(overrides):
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML.
    yaml_path = BASE_DIR / f"config.{ENVIRONMENT}.yaml"
    if yaml_path.exists():
        with yaml_path.open() as file:
            data = yaml.safe_load(file) or {}
        for key, value in data.items():
            config[normalize_key(key)] = value

    # Layer 3: .env file.
    env_file = dotenv_values(BASE_DIR / ".env")
    for key, value in env_file.items():
        if value is not None:
            config[normalize_key(key)] = value

    # Layer 4: OS environment variables.
    for key, value in os.environ.items():
        if key.startswith("APP_") and key != "APP_ENV":
            config[normalize_key(key)] = value

    # Layer 5: repeated CLI-style query overrides.
    for item in overrides:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        config[normalize_key(key)] = value

    # Coerce types after merging so every layer follows the same rules.
    config = {
        key: coerce(key, value)
        for key, value in config.items()
    }

    # Never expose the real secret.
    config["api_key"] = "****"

    return config


@app.get("/effective-config")
def get_effective_config(set: list[str] = Query(default=[])):
    return effective_config(set)


@app.get("/")
def health():
    return {"status": "ok"}
