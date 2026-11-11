"""Load the saved .env before tests decide whether the database is configured."""

from mandate_core.settings import load_env

load_env()
