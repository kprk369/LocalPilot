"""Validated runtime settings. Setup administrator credentials are never loaded here."""
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    token: str
    ssh_host: str
    ssh_key: str
    known_hosts: str
    installer_key: str = ''
    host_key_alias: str = ''
    password_hash: str = ''
    auth_username: str = 'localpilot'
    public_origin: str = ''
    model: str = 'qwen3.8:latest'
    ollama_url: str = 'http://127.0.0.1:11434'
    database: str = str(ROOT / '.local/tasks.sqlite3')

    @classmethod
    def load(cls):
        data = json.loads((ROOT / '.local/runtime.json').read_text())
        result = cls(**data)
        if len(result.token) < 32:
            raise ValueError('API token is too short')
        if result.ollama_url != 'http://127.0.0.1:11434':
            raise ValueError('Initial provider must remain on Windows loopback')
        return result
