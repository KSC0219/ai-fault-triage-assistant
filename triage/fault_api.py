"""Client for the Spring Boot Network Fault Management API.

If FAULT_API_URL is not set, an in-memory mock with the same interface is
used, so the assistant can be demoed without the Java service running.
"""
from __future__ import annotations

import itertools
from datetime import datetime
from typing import Protocol

import httpx

from . import config

VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


class FaultApi(Protocol):
    def create_fault(self, title: str, device_name: str, severity: str,
                     description: str = "", assigned_to: str | None = None) -> dict: ...

    def device_history(self, device_name: str) -> list[dict]: ...

    def open_faults(self) -> list[dict]: ...


class HttpFaultApi:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self._http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def create_fault(self, title, device_name, severity, description="", assigned_to=None):
        resp = self._http.post("/api/faults", json={
            "title": title, "deviceName": device_name, "severity": severity,
            "description": description, "assignedTo": assigned_to,
        })
        resp.raise_for_status()
        return resp.json()

    def device_history(self, device_name):
        resp = self._http.get("/api/faults", params={"device": device_name})
        resp.raise_for_status()
        return resp.json()

    def open_faults(self):
        resp = self._http.get("/api/faults", params={"status": "OPEN"})
        resp.raise_for_status()
        return resp.json()


class MockFaultApi:
    """In-memory stand-in that mirrors the Spring Boot API's JSON shape."""

    def __init__(self):
        self._ids = itertools.count(1)
        self.faults: list[dict] = []

    def create_fault(self, title, device_name, severity, description="", assigned_to=None):
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(VALID_SEVERITIES)}")
        fault = {
            "id": next(self._ids), "title": title, "deviceName": device_name,
            "severity": severity, "description": description, "assignedTo": assigned_to,
            "status": "OPEN", "reportedAt": datetime.now().isoformat(timespec="seconds"),
        }
        self.faults.append(fault)
        return fault

    def device_history(self, device_name):
        return [f for f in self.faults if f["deviceName"].lower() == device_name.lower()]

    def open_faults(self):
        return [f for f in self.faults if f["status"] == "OPEN"]


def get_fault_api() -> FaultApi:
    return HttpFaultApi(config.FAULT_API_URL) if config.FAULT_API_URL else MockFaultApi()
