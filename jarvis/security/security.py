import json
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Risk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Decision:
    allowed: bool
    risk: Risk
    reason: str


class SecurityManager:
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def classify(self, action: str) -> Risk:
        if action in {
            "screen.capture",
            "screen.analyze",
            "system.info",
            "system.time",
            "memory.remember",
            "memory.search",
            "app.open",
        }:
            return Risk.LOW
        if action in {
            "mouse.move",
            "mouse.click",
            "mouse.scroll",
            "window.focus",
            "browser.open",
            "file.list",
        }:
            return Risk.MEDIUM
        if action in {
            "keyboard.type",
            "keyboard.press",
            "keyboard.hotkey",
            "terminal.exec",
            "file.read",
            "file.write",
            "file.rename",
            "file.open",
            "communication.send",
            "communication.call",
        }:
            return Risk.HIGH
        if action in {"file.delete", "system.shutdown", "system.restart"}:
            return Risk.CRITICAL
        return Risk.MEDIUM

    def authorize(
        self,
        action: str,
        interactive=True,
        approved: bool | None = None,
    ) -> Decision:
        risk = self.classify(action)
        if risk == Risk.LOW:
            decision = Decision(True, risk, "low-risk action")
        elif risk == Risk.CRITICAL:
            decision = Decision(False, risk, "critical action is disabled by default")
        elif approved is not None:
            decision = Decision(
                approved,
                risk,
                "user approval" if approved else "user denied",
            )
        elif interactive:
            answer = (
                input(
                    f"JARVIS approval required for {action} [{risk.value}]. "
                    "Allow? [y/N]: "
                )
                .strip()
                .lower()
            )
            decision = Decision(
                answer == "y",
                risk,
                "user approval" if answer == "y" else "user denied",
            )
        else:
            decision = Decision(False, risk, "interactive approval unavailable")
        self._audit(action, decision)
        return decision

    def _audit(self, action, decision):
        record = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "action": action,
            "risk": decision.risk.value,
            "allowed": decision.allowed,
            "reason": decision.reason,
        }
        with self.log_file.open("a", encoding="utf-8") as log:
            log.write(json.dumps(record) + "\n")
