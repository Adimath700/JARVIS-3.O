import time
import uuid
from threading import Condition


class AssistantUiState:
    def __init__(self):
        self._condition = Condition()
        self._agent_state = "offline"
        self._activity = None
        self._message = "Waiting for the voice agent"
        self._user_transcript = ""
        self._assistant_transcript = ""
        self._approvals = {}
        self._trusted_mode = False
        self._manual_turn_control = True

    def set_trusted_mode(self, enabled: bool):
        with self._condition:
            self._trusted_mode = enabled

    def set_manual_turn_control(self, enabled: bool):
        with self._condition:
            self._manual_turn_control = enabled

    def set_agent_state(self, state: str):
        messages = {
            "initializing": "Initializing neural systems",
            "idle": "Ready",
            "listening": "Listening",
            "thinking": "Thinking",
            "speaking": "Speaking",
            "offline": "Voice agent offline",
        }
        with self._condition:
            self._agent_state = state
            if state == "initializing" or (
                self._activity == "error" and state != "offline"
            ):
                self._activity = None
            if self._activity not in {"approval", "tool", "error"}:
                self._message = messages.get(state, state.title())

    def set_status_message(self, message: str):
        with self._condition:
            if self._activity not in {"approval", "tool", "error"}:
                self._message = message

    def set_user_transcript(self, transcript: str):
        with self._condition:
            self._user_transcript = transcript.strip()

    def set_assistant_transcript(self, transcript: str):
        with self._condition:
            self._assistant_transcript = transcript.strip()

    def set_activity(self, activity: str | None, message: str = ""):
        with self._condition:
            self._activity = activity
            if message:
                self._message = message
            elif activity is None:
                self._message = self._agent_state.title()

    def set_error(self, message: str):
        self.set_activity("error", message)

    def request_approval(
        self,
        action: str,
        details: str,
        timeout: float,
    ) -> bool | None:
        request_id = uuid.uuid4().hex
        request = {
            "id": request_id,
            "action": action,
            "details": details,
            "decision": None,
            "created_at": time.time(),
        }
        with self._condition:
            self._approvals[request_id] = request
            self._activity = "approval"
            self._message = f"Approval required: {action}"
            completed = self._condition.wait_for(
                lambda: request["decision"] is not None,
                timeout=timeout,
            )
            approved = bool(request["decision"]) if completed else None
            self._approvals.pop(request_id, None)
            self._activity = None
            self._message = self._agent_state.title()
            return approved

    def resolve_approval(self, request_id: str, approved: bool) -> bool:
        with self._condition:
            request = self._approvals.get(request_id)
            if request is None:
                return False
            request["decision"] = approved
            self._condition.notify_all()
            return True

    def snapshot(self) -> dict:
        with self._condition:
            status = self._activity or self._agent_state
            approvals = [
                {
                    "id": request["id"],
                    "action": request["action"],
                    "details": request["details"],
                }
                for request in self._approvals.values()
                if request["decision"] is None
            ]
            return {
                "status": status,
                "agent_state": self._agent_state,
                "message": self._message,
                "user_transcript": self._user_transcript,
                "assistant_transcript": self._assistant_transcript,
                "approvals": approvals,
                "trusted_mode": self._trusted_mode,
                "manual_turn_control": self._manual_turn_control,
            }


ui_state = AssistantUiState()
