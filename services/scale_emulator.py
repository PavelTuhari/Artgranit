"""
AGRO Scale Emulator — synchronous weight simulation service.

Emulates a weighing scale (e.g., CAS, Mettler Toledo, DIGI) that:
  - produces stable weight readings after settling
  - simulates tare weight memory
  - supports zero/tare/capture operations
  - communicates via a simple in-process API (no serial port needed)

Protocol is modelled on common scale protocols:
  - read()   → current weight reading with stability flag
  - zero()   → zero the scale
  - tare()   → capture current weight as tare
  - capture() → lock the current stable reading

For real hardware integration, replace ScaleEmulator with a class
that reads from serial/USB (e.g., via pyserial) using the same interface.
"""
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional


class ScaleStatus(str, Enum):
    IDLE = "idle"
    SETTLING = "settling"
    STABLE = "stable"
    OVERLOAD = "overload"
    ERROR = "error"


@dataclass
class ScaleReading:
    gross_kg: float
    tare_kg: float
    net_kg: float
    stable: bool
    status: ScaleStatus
    unit: str = "kg"
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gross_kg": round(self.gross_kg, 3),
            "tare_kg": round(self.tare_kg, 3),
            "net_kg": round(self.net_kg, 3),
            "stable": self.stable,
            "status": self.status.value,
            "unit": self.unit,
            "timestamp": self.timestamp,
        }


class ScaleEmulator:
    """Synchronous scale emulator with realistic settling behavior."""

    def __init__(
        self,
        *,
        max_capacity_kg: float = 600.0,
        resolution_kg: float = 0.02,
        settle_time_s: float = 1.5,
        noise_kg: float = 0.05,
        drift_kg: float = 0.01,
    ):
        self.max_capacity_kg = max_capacity_kg
        self.resolution_kg = resolution_kg
        self.settle_time_s = settle_time_s
        self.noise_kg = noise_kg
        self.drift_kg = drift_kg

        self._lock = threading.Lock()
        self._tare_kg: float = 0.0
        self._target_kg: float = 0.0       # simulated load on platform
        self._actual_kg: float = 0.0        # current displayed value
        self._load_time: float = 0.0        # when load was last changed
        self._zero_offset: float = 0.0
        self._captured: Optional[ScaleReading] = None
        self._connected: bool = True

    # ── Public API ────────────────────────────────────────────────

    def read(self) -> ScaleReading:
        """Return current weight reading with stability flag."""
        with self._lock:
            if not self._connected:
                return ScaleReading(
                    gross_kg=0, tare_kg=0, net_kg=0,
                    stable=False, status=ScaleStatus.ERROR,
                )
            self._update_actual()
            gross = max(0.0, self._actual_kg - self._zero_offset)
            gross = round(gross / self.resolution_kg) * self.resolution_kg

            if gross > self.max_capacity_kg:
                return ScaleReading(
                    gross_kg=gross, tare_kg=self._tare_kg,
                    net_kg=gross - self._tare_kg,
                    stable=False, status=ScaleStatus.OVERLOAD,
                )

            elapsed = time.time() - self._load_time
            stable = elapsed >= self.settle_time_s
            status = ScaleStatus.STABLE if stable else ScaleStatus.SETTLING

            return ScaleReading(
                gross_kg=gross,
                tare_kg=self._tare_kg,
                net_kg=max(0.0, gross - self._tare_kg),
                stable=stable,
                status=status,
            )

    def zero(self) -> Dict[str, Any]:
        """Zero the scale (set current weight as zero reference)."""
        with self._lock:
            self._update_actual()
            self._zero_offset = self._actual_kg
            self._tare_kg = 0.0
            self._captured = None
            return {"success": True, "message": "Scale zeroed"}

    def tare(self) -> Dict[str, Any]:
        """Capture current weight as tare."""
        with self._lock:
            self._update_actual()
            gross = max(0.0, self._actual_kg - self._zero_offset)
            self._tare_kg = round(gross / self.resolution_kg) * self.resolution_kg
            self._captured = None
            return {"success": True, "tare_kg": round(self._tare_kg, 3)}

    def capture(self) -> Dict[str, Any]:
        """Lock the current stable reading. Returns error if not stable."""
        reading = self.read()
        if not reading.stable:
            return {"success": False, "error": "Weight not stable", "reading": reading.to_dict()}
        with self._lock:
            self._captured = reading
        return {"success": True, "reading": reading.to_dict()}

    def get_captured(self) -> Optional[Dict[str, Any]]:
        """Return the last captured reading, or None."""
        with self._lock:
            if self._captured:
                return self._captured.to_dict()
            return None

    def clear_captured(self):
        """Clear the captured reading."""
        with self._lock:
            self._captured = None

    # ── Simulation control (for emulator only) ────────────────────

    def simulate_load(self, weight_kg: float) -> Dict[str, Any]:
        """Place a simulated weight on the scale platform."""
        with self._lock:
            self._target_kg = max(0.0, weight_kg)
            self._load_time = time.time()
            self._captured = None
            return {"success": True, "target_kg": round(self._target_kg, 3)}

    def simulate_remove(self) -> Dict[str, Any]:
        """Remove all weight from the platform."""
        return self.simulate_load(0.0)

    def simulate_random_load(
        self, min_kg: float = 5.0, max_kg: float = 50.0
    ) -> Dict[str, Any]:
        """Place a random weight on the platform (useful for demo/testing)."""
        w = round(random.uniform(min_kg, max_kg), 2)
        return self.simulate_load(w)

    def set_connected(self, connected: bool):
        """Simulate connecting/disconnecting the scale."""
        with self._lock:
            self._connected = connected

    def get_config(self) -> Dict[str, Any]:
        """Return scale configuration."""
        return {
            "max_capacity_kg": self.max_capacity_kg,
            "resolution_kg": self.resolution_kg,
            "settle_time_s": self.settle_time_s,
            "unit": "kg",
            "connected": self._connected,
            "emulator": True,
        }

    # ── Internal ──────────────────────────────────────────────────

    def _update_actual(self):
        """Simulate the scale value approaching target with noise."""
        elapsed = time.time() - self._load_time
        if elapsed >= self.settle_time_s:
            # Settled — small noise only
            noise = random.gauss(0, self.drift_kg)
            self._actual_kg = self._target_kg + noise
        else:
            # Settling — exponential approach with larger noise
            progress = min(1.0, elapsed / self.settle_time_s)
            approach = 1 - (1 - progress) ** 3  # cubic ease-out
            diff = self._target_kg - self._actual_kg
            noise = random.gauss(0, self.noise_kg * (1 - progress))
            self._actual_kg += diff * approach * 0.3 + noise


# ── Singleton registry for multiple scale instances ──────────────

_scales: Dict[str, ScaleEmulator] = {}
_registry_lock = threading.Lock()


def get_scale(scale_id: str = "default") -> ScaleEmulator:
    """Get or create a scale emulator by ID."""
    with _registry_lock:
        if scale_id not in _scales:
            _scales[scale_id] = ScaleEmulator()
        return _scales[scale_id]


def list_scales() -> list[str]:
    """List all registered scale IDs."""
    with _registry_lock:
        return list(_scales.keys())


def create_scale(scale_id: str, **kwargs) -> ScaleEmulator:
    """Create a new scale with custom parameters."""
    with _registry_lock:
        _scales[scale_id] = ScaleEmulator(**kwargs)
        return _scales[scale_id]
