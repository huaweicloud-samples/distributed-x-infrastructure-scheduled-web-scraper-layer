"""Runtime configuration read from the function environment."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    region: str = "cn-north-4"
    obs_bucket: str = ""
    obs_endpoint: str = ""
    target_url: str = "https://www.example.com"
    result_prefix: str = "snapshots"
    service_name: str = "scheduled-web-scraper"
    log_level: str = "INFO"
    lts_group_id: str = ""
    lts_stream_id: str = ""
    timer_schedule: str = ""


_FIELDS = {
    "region": "REGION",
    "obs_bucket": "OBS_BUCKET",
    "obs_endpoint": "OBS_ENDPOINT",
    "target_url": "TARGET_URL",
    "result_prefix": "RESULT_PREFIX",
    "service_name": "SERVICE_NAME",
    "log_level": "LOG_LEVEL",
    "lts_group_id": "LTS_GROUP_ID",
    "lts_stream_id": "LTS_STREAM_ID",
    "timer_schedule": "TIMER_SCHEDULE",
}


def load_config(env=None):
    """Build a Config from an environment mapping, keeping defaults for blanks."""
    env = env if env is not None else {}
    values = {}
    for field, key in _FIELDS.items():
        raw = env.get(key)
        if raw is not None and str(raw).strip() != "":
            values[field] = str(raw)
    return Config(**values)
