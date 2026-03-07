import datetime
import json
import os
import tempfile
import uuid


class RecoveryManager:
    SCHEMA_VERSION = 1

    def __init__(
        self,
        *,
        enabled: bool = True,
        interval_seconds: int = 30,
        max_snapshots: int = 20,
        recovery_dir: str = "pyword_recovery",
        session_id: str | None = None,
    ):
        self.enabled = bool(enabled)
        self.interval_seconds = max(5, int(interval_seconds))
        self.max_snapshots = max(1, int(max_snapshots))
        self.recovery_dir = str(recovery_dir or "pyword_recovery").strip() or "pyword_recovery"
        self.session_id = str(session_id or uuid.uuid4().hex)
        self._state_path = os.path.join(self.recovery_dir, "recovery_state.json")
        self._previous_state = self._read_state()
        self._previous_unclean = not bool(self._previous_state.get("clean_shutdown", True))
        self._previous_session_id = str(self._previous_state.get("active_session_id", "") or "").strip()
        if self.enabled:
            self._ensure_recovery_dir()
            self._write_state(clean_shutdown=False)

    @classmethod
    def from_settings(cls, settings: dict | None):
        data = settings if isinstance(settings, dict) else {}

        def _safe_bool(value, fallback: bool):
            if value is None:
                return bool(fallback)
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            text = str(value).strip().lower()
            if text in {"1", "true", "yes", "on"}:
                return True
            if text in {"0", "false", "no", "off"}:
                return False
            return bool(fallback)

        def _safe_int(value, fallback: int, minimum: int, maximum: int):
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                parsed = int(fallback)
            return max(minimum, min(maximum, parsed))

        def _safe_path(value, fallback: str):
            text = str(value or "").strip()
            return text or str(fallback)

        return cls(
            enabled=_safe_bool(data.get("enabled"), True),
            interval_seconds=_safe_int(data.get("interval_seconds"), 30, 5, 900),
            max_snapshots=_safe_int(data.get("max_snapshots"), 20, 1, 500),
            recovery_dir=_safe_path(data.get("recovery_dir"), "pyword_recovery"),
        )

    def save_snapshot(self, text: str, context: dict | None) -> str | None:
        if not self.enabled:
            return None
        self._ensure_recovery_dir()
        now = datetime.datetime.utcnow().replace(microsecond=0)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "snapshot_id": uuid.uuid4().hex,
            "session_id": self.session_id,
            "timestamp_utc": now.isoformat() + "Z",
            "text": str(text or ""),
            "context": context if isinstance(context, dict) else {},
        }
        file_name = f"snapshot_{now.strftime('%Y%m%dT%H%M%S')}_{payload['snapshot_id']}.json"
        out_path = os.path.join(self.recovery_dir, file_name)
        self._atomic_write_json(out_path, payload)
        self._prune_snapshots()
        return out_path

    def latest_snapshot(self) -> dict | None:
        if not self.enabled:
            return None
        if not self._previous_unclean or not self._previous_session_id:
            return None
        return self._latest_snapshot_for_session(self._previous_session_id)

    def clear_session_snapshots(self) -> None:
        if not self.enabled:
            return
        for path in self._snapshot_paths():
            payload = self._read_json(path)
            if not isinstance(payload, dict):
                continue
            if str(payload.get("session_id", "")).strip() != self.session_id:
                continue
            try:
                os.remove(path)
            except OSError:
                pass

    def mark_clean_shutdown(self) -> None:
        if not self.enabled:
            return
        self._write_state(clean_shutdown=True)

    def _ensure_recovery_dir(self):
        os.makedirs(self.recovery_dir, mode=0o700, exist_ok=True)
        try:
            os.chmod(self.recovery_dir, 0o700)
        except OSError:
            pass

    def _write_state(self, *, clean_shutdown: bool):
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "active_session_id": self.session_id,
            "clean_shutdown": bool(clean_shutdown),
            "updated_utc": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        self._atomic_write_json(self._state_path, payload)

    def _read_state(self) -> dict:
        payload = self._read_json(self._state_path)
        return payload if isinstance(payload, dict) else {}

    def _snapshot_paths(self):
        if not os.path.isdir(self.recovery_dir):
            return []
        paths = []
        for name in os.listdir(self.recovery_dir):
            if not name.startswith("snapshot_") or not name.endswith(".json"):
                continue
            paths.append(os.path.join(self.recovery_dir, name))
        paths.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0.0, reverse=True)
        return paths

    def _latest_snapshot_for_session(self, session_id: str):
        sid = str(session_id or "").strip()
        if not sid:
            return None
        for path in self._snapshot_paths():
            payload = self._read_json(path)
            if not isinstance(payload, dict):
                continue
            if str(payload.get("session_id", "")).strip() != sid:
                continue
            return payload
        return None

    def _prune_snapshots(self):
        paths = self._snapshot_paths()
        for stale_path in paths[self.max_snapshots :]:
            try:
                os.remove(stale_path)
            except OSError:
                pass

    def _atomic_write_json(self, path: str, payload: dict):
        directory = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(directory, mode=0o700, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".pyword_recovery_", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _read_json(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None
