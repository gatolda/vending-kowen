"""
CLI del firmware. Dos sub-comandos:

  edge-water run        # producción: hardware real (en la Pi) + MQTT real
  edge-water simulate   # desarrollo: hardware mock + bus in-memory + UI interactiva
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from edge_water.app import build_bus, build_mock_hardware, build_real_hardware, decode_event, App
from edge_water.bus import InMemoryBus
from edge_water.config import Settings
from edge_water.hardware.mock import MockFlowMeter, MockFlowMeterConfig
from edge_water.messages import (
    CMD_ABORT,
    CMD_DISPENSE,
    AbortCommand,
    DispenseCommand,
    DispenseFailed,
    DispenseProgress,
)

app = typer.Typer(add_completion=False, help="Edge water dispenser firmware")
console = Console()


def _setup_logging(verbose: bool) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=level, format="<dim>{time:HH:mm:ss}</dim> <level>{message}</level>")


@app.command()
def run(verbose: Annotated[bool, typer.Option("-v", "--verbose")] = False) -> None:
    """Corre el firmware en modo producción (lee de .env)."""
    _setup_logging(verbose)
    settings = Settings()
    asyncio.run(_run_production(settings))


async def _run_production(settings: Settings) -> None:
    if settings.hardware_mode == "real":
        hw = build_real_hardware(settings)
    else:
        hw = build_mock_hardware()
    bus = build_bus(settings)
    application = App(settings, hw, bus)
    await application.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await application.stop()


@app.command()
def simulate(
    machine_id: Annotated[str, typer.Option(help="ID lógico de la máquina")] = "water-sim",
    pulses_per_liter: Annotated[float, typer.Option()] = 450.0,
    no_flow_timeout: Annotated[float, typer.Option(help="Seg sin pulsos = atasco")] = 5.0,
    verbose: Annotated[bool, typer.Option("-v", "--verbose")] = False,
) -> None:
    """Simulador interactivo. No requiere hardware ni broker MQTT."""
    _setup_logging(verbose)
    settings = Settings(
        machine_id=machine_id,
        hardware_mode="mock",
        bus_mode="memory",
        pulses_per_liter=pulses_per_liter,
        no_flow_timeout_s=no_flow_timeout,
        progress_interval_ms=500,
        heartbeat_interval_s=60.0,
    )
    asyncio.run(_run_simulator(settings))


async def _run_simulator(settings: Settings) -> None:
    bus = InMemoryBus()
    hw = build_mock_hardware()
    flow_meter: MockFlowMeter = hw.flow_meter  # type: ignore[assignment]
    application = App(settings, hw, bus)
    await application.start()

    # Suscribir el "backend" simulado a todos los eventos para imprimirlos.
    prefix = settings.topic_prefix
    last_progress_pct = -1

    async def on_event(topic: str, payload: bytes) -> None:
        nonlocal last_progress_pct
        evt = decode_event(topic, payload)
        if evt is None:
            return
        if isinstance(evt, DispenseProgress):
            pct = int(evt.percent)
            if pct == last_progress_pct:
                return
            last_progress_pct = pct
            console.print(f"  [cyan]progreso[/]  {evt.liters_so_far:.3f} L  ({pct}%)")
            return
        last_progress_pct = -1
        kind = type(evt).__name__
        if kind == "Heartbeat":
            return  # ruidoso para la UI; ya se loguea
        if isinstance(evt, DispenseFailed):
            console.print(f"  [red]✗ {kind}[/]  reason={evt.reason.value}  parcial={evt.liters_partial:.3f} L  {evt.detail or ''}")
        else:
            color = "green" if "Completed" in kind or "Started" in kind else "yellow"
            data = evt.model_dump(exclude={"machine_id", "ts", "type"})
            console.print(f"  [{color}]✓ {kind}[/]  {data}")

    await bus.subscribe(f"{prefix}/event/#", on_event)

    console.print(
        Panel.fit(
            f"[bold]Simulador edge-water[/]\nmáquina: [cyan]{settings.machine_id}[/]\n"
            f"pulsos/L: {settings.pulses_per_liter}   no-flow timeout: {settings.no_flow_timeout_s}s",
            title="ready",
            border_style="green",
        )
    )

    try:
        while True:
            choice = await _menu()
            if choice == "0":
                break
            await _dispatch(choice, bus, prefix, application, flow_meter)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        await application.stop()
        flow_meter.shutdown()
        console.print("\n[dim]bye[/]")


def _print_menu() -> None:
    console.print(
        "\n"
        "[bold]Acciones[/]:\n"
        "  1) Dispensar 0.5 L\n"
        "  2) Dispensar 1 L\n"
        "  3) Dispensar 2.5 L\n"
        "  4) Dispensar litros custom\n"
        "  5) Abortar orden activa\n"
        "  ─── Inyección de fallas (caudalímetro mock) ───\n"
        "  6) Atasco total (stuck = sin pulsos)\n"
        "  7) Goteo sin orden (leak)\n"
        "  8) Atasco a mitad (stop_after_pulses)\n"
        "  9) Caudal lento (1/4 de velocidad)\n"
        "  r) Resetear caudalímetro a estado normal\n"
        "  0) Salir\n"
    )


async def _menu() -> str:
    _print_menu()
    return (await asyncio.to_thread(input, "> ")).strip().lower()


async def _dispatch(
    choice: str,
    bus: InMemoryBus,
    prefix: str,
    application: App,
    flow_meter: MockFlowMeter,
) -> None:
    if choice in {"1", "2", "3", "4"}:
        liters = {"1": 0.5, "2": 1.0, "3": 2.5}.get(choice)
        if choice == "4":
            raw = (await asyncio.to_thread(input, "Litros: ")).strip()
            try:
                liters = float(raw)
            except ValueError:
                console.print("[red]litros inválidos[/]")
                return
        assert liters is not None
        order_id = f"sim-{uuid.uuid4().hex[:8]}"
        cmd = DispenseCommand(order_id=order_id, liters=liters)
        console.print(f"\n[bold]→ enviando dispense {liters} L (orden {order_id})[/]")
        await bus.publish(f"{prefix}/{CMD_DISPENSE}", cmd.model_dump_json().encode())
        return

    if choice == "5":
        active = application.dispenser.active_order_id
        if not active:
            console.print("[yellow]no hay orden activa[/]")
            return
        console.print(f"[bold]→ abort orden {active}[/]")
        await bus.publish(
            f"{prefix}/{CMD_ABORT}",
            AbortCommand(order_id=active, reason="manual").model_dump_json().encode(),
        )
        return

    if choice == "6":
        flow_meter.configure(MockFlowMeterConfig(stuck=True))
        console.print("[yellow]inyectado: stuck[/]")
        return
    if choice == "7":
        flow_meter.configure(MockFlowMeterConfig(leak_rate=10.0))
        console.print("[yellow]inyectado: leak 10 pulsos/s[/]")
        return
    if choice == "8":
        flow_meter.configure(MockFlowMeterConfig(stop_after_pulses=200))
        console.print("[yellow]inyectado: stop_after_pulses=200[/]")
        return
    if choice == "9":
        flow_meter.configure(MockFlowMeterConfig(pulses_per_second=18.0))
        console.print("[yellow]inyectado: caudal lento[/]")
        return
    if choice == "r":
        flow_meter.configure(MockFlowMeterConfig())
        flow_meter.reset()
        console.print("[green]caudalímetro reseteado[/]")
        return

    console.print("[red]opción inválida[/]")


if __name__ == "__main__":
    app()
