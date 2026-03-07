class SecretStoreError(RuntimeError):
    pass


class SecretStore:
    def __init__(self, service_name: str = "PyWord Pro", keyring_module=None):
        self.service_name = str(service_name or "PyWord Pro")
        self._keyring = keyring_module
        if self._keyring is None:
            try:
                import keyring  # type: ignore

                self._keyring = keyring
            except Exception:
                self._keyring = None

    @property
    def available(self) -> bool:
        return self._keyring is not None

    def get_secret(self, name: str) -> str:
        if not self.available:
            raise SecretStoreError("Secure secret storage is unavailable.")
        key = str(name or "").strip()
        if not key:
            raise SecretStoreError("Secret key is required.")
        try:
            value = self._keyring.get_password(self.service_name, key)
        except Exception as exc:
            raise SecretStoreError(f"Secret lookup failed: {exc}") from exc
        return str(value or "")

    def set_secret(self, name: str, value: str) -> None:
        if not self.available:
            raise SecretStoreError("Secure secret storage is unavailable.")
        key = str(name or "").strip()
        if not key:
            raise SecretStoreError("Secret key is required.")
        secret = str(value or "").strip()
        if not secret:
            raise SecretStoreError("Secret value cannot be empty.")
        try:
            self._keyring.set_password(self.service_name, key, secret)
        except Exception as exc:
            raise SecretStoreError(f"Secret storage failed: {exc}") from exc

    def delete_secret(self, name: str) -> None:
        if not self.available:
            return
        key = str(name or "").strip()
        if not key:
            return
        try:
            self._keyring.delete_password(self.service_name, key)
        except Exception:
            # Delete should be best-effort.
            return
