from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    machine_id: str = "water-dev"
    hardware_mode: Literal["real", "mock"] = "mock"
    bus_mode: Literal["memory", "mqtt"] = "memory"

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_tls: bool = False
    mqtt_username: str | None = None
    mqtt_password: str | None = None

    pulses_per_liter: float = 450.0

    gpio_flow_meter: int = 17
    gpio_valve: int = 23
    gpio_pump: int = 24
    gpio_led: int = 18
    relay_active_low: bool = True

    dispense_timeout_s: float = 120.0
    no_flow_timeout_s: float = 5.0
    progress_interval_ms: int = 500
    heartbeat_interval_s: float = 30.0

    @property
    def topic_prefix(self) -> str:
        return f"machines/{self.machine_id}"
