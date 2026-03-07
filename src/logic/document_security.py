import datetime
import hashlib
import io
import json
import os
import tempfile
import zipfile


class DocumentSecurityError(RuntimeError):
    pass


class DocumentSecurityScanner:
    BLOCKED_OFFICE_EXTENSIONS = {
        ".doc",
        ".docm",
        ".dotm",
        ".xls",
        ".xlsm",
        ".xltm",
        ".ppt",
        ".pptm",
        ".potm",
    }
    ALLOWED_EXTENSIONS = {".txt", ".docx"}
    OFFICE_EXTENSIONS = BLOCKED_OFFICE_EXTENSIONS | {".docx", ".dotx"}
    ZIP_MAGIC_HEADERS = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
    OLE_MAGIC_HEADER = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

    def __init__(
        self,
        *,
        strict_mode: bool = True,
        max_input_bytes: int = 16 * 1024 * 1024,
        max_zip_entries: int = 2500,
        max_zip_uncompressed_bytes: int = 48 * 1024 * 1024,
        max_zip_compression_ratio: int = 200,
        block_encrypted_office: bool = True,
        require_oletools: bool = False,
        require_msoffcrypto: bool = False,
        require_yara_rules: bool = False,
        require_clamav: bool = False,
        yara_rules_path: str | None = None,
        quarantine_enabled: bool = True,
        quarantine_dir: str = "pyword_quarantine",
        audit_log_path: str = "pyword_security_audit.log",
    ):
        self.strict_mode = bool(strict_mode)
        self.max_input_bytes = max(1024, int(max_input_bytes))
        self.max_zip_entries = max(1, int(max_zip_entries))
        self.max_zip_uncompressed_bytes = max(1024 * 1024, int(max_zip_uncompressed_bytes))
        self.max_zip_compression_ratio = max(1, int(max_zip_compression_ratio))
        self.block_encrypted_office = bool(block_encrypted_office)
        self.require_oletools = bool(require_oletools)
        self.require_msoffcrypto = bool(require_msoffcrypto)
        self.require_yara_rules = bool(require_yara_rules)
        self.require_clamav = bool(require_clamav)

        configured_yara_path = (yara_rules_path or os.environ.get("PYWORD_YARA_RULES", "")).strip()
        self.yara_rules_path = configured_yara_path
        self.clamav_enabled = self.require_clamav or str(os.environ.get("PYWORD_CLAMAV_SCAN", "")).strip().lower() in {"1", "true", "yes", "on"}
        self.oletools_enabled = str(os.environ.get("PYWORD_OLETOOLS_SCAN", "1")).strip().lower() not in {"0", "false", "no", "off"}
        if self.require_oletools:
            self.oletools_enabled = True

        self.quarantine_enabled = bool(quarantine_enabled)
        self.quarantine_dir = str(quarantine_dir or "").strip()
        self.audit_log_path = str(audit_log_path or "").strip()
        self._yara_rules = None
        self._clamd_client = None
        self._runtime_issues_cache = None

    @classmethod
    def from_settings(cls, settings: dict | None):
        data = settings if isinstance(settings, dict) else {}

        def _to_bool(key: str, default: bool) -> bool:
            value = data.get(key, default)
            if value is None:
                return bool(default)
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            text = str(value).strip().lower()
            if text in {"1", "true", "yes", "on"}:
                return True
            if text in {"0", "false", "no", "off"}:
                return False
            return bool(default)

        def _to_int(key: str, default: int, low: int, high: int) -> int:
            value = data.get(key, default)
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                parsed = int(default)
            return max(low, min(high, parsed))

        max_input_mb = _to_int("max_input_mb", 16, 1, 512)
        max_docx_entries = _to_int("max_docx_entries", 2500, 100, 50000)
        max_docx_uncompressed_mb = _to_int("max_docx_uncompressed_mb", 48, 8, 2048)
        max_docx_compression_ratio = _to_int("max_docx_compression_ratio", 200, 10, 2000)

        return cls(
            strict_mode=_to_bool("strict_mode", True),
            max_input_bytes=max_input_mb * 1024 * 1024,
            max_zip_entries=max_docx_entries,
            max_zip_uncompressed_bytes=max_docx_uncompressed_mb * 1024 * 1024,
            max_zip_compression_ratio=max_docx_compression_ratio,
            block_encrypted_office=_to_bool("block_encrypted_office", True),
            require_oletools=_to_bool("require_oletools", False),
            require_msoffcrypto=_to_bool("require_msoffcrypto", False),
            require_yara_rules=_to_bool("require_yara_rules", False),
            require_clamav=_to_bool("require_clamav", False),
            yara_rules_path=str(data.get("yara_rules_path", "") or "").strip() or None,
            quarantine_enabled=_to_bool("quarantine_enabled", True),
            quarantine_dir=str(data.get("quarantine_dir", "pyword_quarantine") or "").strip() or "pyword_quarantine",
            audit_log_path=str(data.get("audit_log_path", "pyword_security_audit.log") or "").strip(),
        )

    def scan_file(self, path: str, extension: str | None = None) -> None:
        file_path = (path or "").strip()
        if not file_path:
            raise DocumentSecurityError("Document path is missing.")
        if not os.path.exists(file_path):
            raise DocumentSecurityError("Document does not exist.")
        if self.strict_mode and os.path.islink(file_path):
            raise DocumentSecurityError("Symbolic links are blocked in strict mode.")

        stat = os.stat(file_path)
        if stat.st_size > self.max_input_bytes:
            message = self._size_error_message(stat.st_size)
            self._audit(
                result="block",
                source_name=os.path.basename(file_path),
                extension=(extension or os.path.splitext(file_path)[1] or "").lower(),
                size_bytes=int(stat.st_size),
                sha256="",
                reason=message,
                quarantine_path="",
            )
            raise DocumentSecurityError(message)

        with open(file_path, "rb") as handle:
            payload = handle.read(self.max_input_bytes + 1)
        if len(payload) > self.max_input_bytes:
            message = self._size_error_message(len(payload))
            self._audit(
                result="block",
                source_name=os.path.basename(file_path),
                extension=(extension or os.path.splitext(file_path)[1] or "").lower(),
                size_bytes=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
                reason=message,
                quarantine_path="",
            )
            raise DocumentSecurityError(message)

        ext = (extension or os.path.splitext(file_path)[1]).strip().lower()
        source_name = os.path.basename(file_path) or file_path
        self.scan_bytes(payload, source_name=source_name, extension=ext)

    def scan_bytes(self, payload: bytes, *, source_name: str, extension: str) -> None:
        blob = payload or b""
        source_label = os.path.basename(str(source_name or "document")).strip() or "document"
        ext = self._normalize_extension(extension)
        digest = hashlib.sha256(blob).hexdigest() if blob else ""

        try:
            self._scan_bytes_impl(blob, extension=ext, source_name=source_label)
        except DocumentSecurityError as exc:
            quarantine_path = self._quarantine(blob, ext, digest=digest)
            self._audit(
                result="block",
                source_name=source_label,
                extension=ext,
                size_bytes=len(blob),
                sha256=digest,
                reason=str(exc),
                quarantine_path=quarantine_path,
            )
            raise

        self._audit(
            result="allow",
            source_name=source_label,
            extension=ext,
            size_bytes=len(blob),
            sha256=digest,
            reason="",
            quarantine_path="",
        )

    def _scan_bytes_impl(self, payload: bytes, *, extension: str, source_name: str) -> None:
        if len(payload) > self.max_input_bytes:
            raise DocumentSecurityError(self._size_error_message(len(payload)))

        if extension in self.BLOCKED_OFFICE_EXTENSIONS:
            raise DocumentSecurityError(
                f"Macro-enabled or legacy Office format blocked ({extension}). Use .docx or .txt only."
            )
        if extension not in self.ALLOWED_EXTENSIONS:
            raise DocumentSecurityError(f"Unsupported document extension: {extension or '<none>'}.")

        if extension == ".txt":
            self._scan_text(payload)
        elif extension == ".docx":
            self._scan_docx_signature(payload)
            self._scan_docx_structure(payload)

        self._scan_encryption(payload, extension=extension)
        self._scan_with_oletools(payload, source_name=source_name, extension=extension)
        self._scan_with_yara(payload)
        self._scan_with_clamav(payload)

    def runtime_issues(self, *, refresh: bool = False) -> list[str]:
        if self._runtime_issues_cache is not None and not refresh:
            return list(self._runtime_issues_cache)

        issues = []
        if self.require_oletools:
            try:
                from oletools import olevba  # type: ignore  # noqa: F401
            except Exception:
                issues.append("oletools is required by policy but not installed.")

        if self.require_msoffcrypto:
            try:
                import msoffcrypto  # type: ignore  # noqa: F401
            except Exception:
                issues.append("msoffcrypto-tool is required by policy but not installed.")

        if self.require_yara_rules:
            if not self.yara_rules_path:
                issues.append("YARA rules are required by policy but no rules file is configured.")
            elif not os.path.exists(self.yara_rules_path):
                issues.append(f"YARA rules file not found: {self.yara_rules_path}")
            else:
                try:
                    import yara  # type: ignore

                    yara.compile(filepath=self.yara_rules_path)
                except Exception:
                    issues.append("YARA rules could not be compiled.")

        if self.require_clamav:
            try:
                import pyclamd  # type: ignore  # noqa: F401
            except Exception:
                issues.append("pyclamd is required by policy but not installed.")

        self._runtime_issues_cache = list(issues)
        return list(issues)

    def _scan_text(self, payload: bytes) -> None:
        sample = payload[:8192]
        if b"\x00" in sample:
            raise DocumentSecurityError("Text file appears to contain binary data.")
        if sample.startswith(self.OLE_MAGIC_HEADER) or sample.startswith(b"MZ") or sample.startswith(self.ZIP_MAGIC_HEADERS):
            raise DocumentSecurityError("Text file signature does not match plain text content.")
        if self.strict_mode and self._has_disallowed_controls(sample):
            raise DocumentSecurityError("Text file contains disallowed control characters.")

    def _scan_docx_signature(self, payload: bytes) -> None:
        if not payload.startswith(self.ZIP_MAGIC_HEADERS):
            raise DocumentSecurityError("DOCX signature is invalid.")

    def _scan_docx_structure(self, payload: bytes) -> None:
        required_parts = {"[content_types].xml", "word/document.xml"}
        found_parts = set()
        try:
            with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
                infos = archive.infolist()
                if len(infos) > self.max_zip_entries:
                    raise DocumentSecurityError(f"DOCX has too many archive entries ({len(infos)}).")

                total_uncompressed = 0
                for info in infos:
                    raw_name = str(info.filename or "")
                    if not raw_name:
                        continue
                    normalized = raw_name.replace("\\", "/")
                    lowered = normalized.lower()
                    found_parts.add(lowered)
                    if normalized.startswith("/") or ".." in normalized.split("/"):
                        raise DocumentSecurityError("DOCX contains an unsafe archive path.")

                    size = max(0, int(getattr(info, "file_size", 0)))
                    compressed_size = max(1, int(getattr(info, "compress_size", 0)))
                    total_uncompressed += size
                    if total_uncompressed > self.max_zip_uncompressed_bytes:
                        raise DocumentSecurityError("DOCX expands beyond allowed uncompressed size.")
                    if size > 0 and (float(size) / float(compressed_size)) > float(self.max_zip_compression_ratio):
                        raise DocumentSecurityError("DOCX contains suspicious compression ratio (possible zip bomb).")

                    if lowered.endswith("vbaproject.bin"):
                        raise DocumentSecurityError("VBA macro payload detected in DOCX.")
                    if "/embeddings/" in lowered or "oleobject" in lowered:
                        raise DocumentSecurityError("Embedded OLE object detected in DOCX.")

                    if lowered.endswith(".rels"):
                        rel_data = archive.read(info, pwd=None)
                        if self._has_external_relationship(rel_data):
                            raise DocumentSecurityError("External relationship detected in DOCX.")

                    if lowered.startswith("word/") and lowered.endswith(".xml"):
                        xml_data = archive.read(info, pwd=None)
                        xml_snippet = xml_data[:300000].upper()
                        if b"DDEAUTO" in xml_snippet or b" DDE " in xml_snippet:
                            raise DocumentSecurityError("DDE link indicator detected in DOCX.")

                missing = required_parts - found_parts
                if missing:
                    raise DocumentSecurityError("DOCX is missing required package parts.")
        except zipfile.BadZipFile as exc:
            raise DocumentSecurityError("Malformed DOCX container.") from exc
        except RuntimeError as exc:
            # Raised by zip decryption requests; treat as suspicious for unsupported encrypted zip/docx.
            raise DocumentSecurityError("Encrypted ZIP/DOCX payload is not supported.") from exc

    def _scan_encryption(self, payload: bytes, *, extension: str) -> None:
        if extension not in self.OFFICE_EXTENSIONS:
            return
        try:
            import msoffcrypto  # type: ignore
        except Exception as exc:
            if self.require_msoffcrypto:
                raise DocumentSecurityError("msoffcrypto-tool is required but not installed.") from exc
            return

        try:
            office_file = msoffcrypto.OfficeFile(io.BytesIO(payload))
        except Exception:
            return
        try:
            if office_file.is_encrypted() and self.block_encrypted_office:
                raise DocumentSecurityError("Encrypted Office document is blocked. Decrypt before import.")
        except DocumentSecurityError:
            raise
        except Exception:
            return

    def _scan_with_oletools(self, payload: bytes, *, source_name: str, extension: str) -> None:
        if not self.oletools_enabled:
            if self.require_oletools:
                raise DocumentSecurityError("oletools scan is required by policy.")
            return
        if extension not in self.OFFICE_EXTENSIONS:
            return
        try:
            from oletools.olevba import VBA_Parser  # type: ignore
        except Exception as exc:
            if self.require_oletools:
                raise DocumentSecurityError("oletools is required but not installed.") from exc
            return

        suffix = extension if extension else ".docx"
        tmp_path = ""
        parser = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                tmp_path = handle.name
                handle.write(payload)
            try:
                os.chmod(tmp_path, 0o600)
            except OSError:
                pass

            parser = VBA_Parser(tmp_path)
            if parser.detect_vba_macros():
                raise DocumentSecurityError(f"VBA macros detected in {source_name}.")
            try:
                for _filename, _stream_path, _vba_filename, code in parser.extract_macros():
                    script = str(code or "").upper()
                    if any(pattern in script for pattern in ("AUTOOPEN", "SHELL(", "CREATEOBJECT(", "WScript.Shell".upper())):
                        raise DocumentSecurityError("Suspicious VBA macro patterns detected.")
            except DocumentSecurityError:
                raise
            except Exception:
                # If macro extraction fails unexpectedly, the default detector already ran.
                pass
        finally:
            try:
                if parser is not None:
                    parser.close()
            except Exception:
                pass
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _scan_with_yara(self, payload: bytes) -> None:
        if not self.yara_rules_path:
            if self.require_yara_rules:
                raise DocumentSecurityError("YARA rules are required by policy but no rules file was configured.")
            return
        if not os.path.exists(self.yara_rules_path):
            raise DocumentSecurityError(f"YARA rules file not found: {self.yara_rules_path}")
        try:
            import yara  # type: ignore
        except Exception as exc:
            raise DocumentSecurityError("YARA scan requested but yara-python is unavailable.") from exc

        if self._yara_rules is None:
            try:
                self._yara_rules = yara.compile(filepath=self.yara_rules_path)
            except Exception as exc:
                raise DocumentSecurityError(f"Could not compile YARA rules: {exc}") from exc

        try:
            matches = self._yara_rules.match(data=payload)
        except Exception as exc:
            raise DocumentSecurityError(f"YARA scan failed: {exc}") from exc
        if matches:
            labels = []
            for match in matches[:5]:
                labels.append(str(getattr(match, "rule", match)))
            marker = ", ".join(labels) if labels else "unknown"
            raise DocumentSecurityError(f"YARA scan matched suspicious signatures: {marker}")

    def _scan_with_clamav(self, payload: bytes) -> None:
        if not self.clamav_enabled:
            if self.require_clamav:
                raise DocumentSecurityError("ClamAV scan is required by policy.")
            return
        try:
            import pyclamd  # type: ignore
        except Exception as exc:
            raise DocumentSecurityError("ClamAV scan requested but pyclamd is unavailable.") from exc

        if self._clamd_client is None:
            client = None
            try:
                client = pyclamd.ClamdAgnostic()
            except Exception:
                try:
                    client = pyclamd.ClamdUnixSocket()
                except Exception:
                    try:
                        client = pyclamd.ClamdNetworkSocket(
                            host=os.environ.get("CLAMD_HOST", "127.0.0.1"),
                            port=int(os.environ.get("CLAMD_PORT", "3310")),
                        )
                    except Exception as exc:
                        raise DocumentSecurityError(f"Could not connect to ClamAV daemon: {exc}") from exc
            try:
                client.ping()
            except Exception as exc:
                raise DocumentSecurityError(f"ClamAV daemon is unavailable: {exc}") from exc
            self._clamd_client = client

        try:
            result = self._clamd_client.scan_stream(payload)
        except Exception as exc:
            raise DocumentSecurityError(f"ClamAV scan failed: {exc}") from exc
        if not result:
            return
        for _target, value in result.items():
            if isinstance(value, tuple) and len(value) >= 2 and str(value[0]).upper() == "FOUND":
                raise DocumentSecurityError(f"ClamAV detected malware signature: {value[1]}")
            if isinstance(value, str) and value:
                raise DocumentSecurityError(f"ClamAV detected malware signature: {value}")

    def _has_external_relationship(self, rel_data: bytes) -> bool:
        try:
            from defusedxml import ElementTree as safe_xml  # type: ignore

            root = safe_xml.fromstring(rel_data)
            for node in root.findall(".//{*}Relationship"):
                mode = str(node.attrib.get("TargetMode", "")).strip().lower()
                if mode == "external":
                    return True
            return False
        except Exception:
            snippet = (rel_data or b"")[:200000].lower()
            return b"targetmode=\"external\"" in snippet

    def _normalize_extension(self, extension: str) -> str:
        ext = str(extension or "").strip().lower()
        if not ext:
            return ""
        if not ext.startswith("."):
            ext = f".{ext}"
        return ext

    def _has_disallowed_controls(self, payload: bytes) -> bool:
        for value in payload:
            if value in (9, 10, 13):
                continue
            if value < 32:
                return True
        return False

    def _safe_quarantine_extension(self, extension: str) -> str:
        ext = self._normalize_extension(extension)
        if not ext:
            return ".bin"
        safe = "".join(ch for ch in ext if ch.isalnum() or ch == ".")
        if not safe.startswith(".") or len(safe) > 16:
            return ".bin"
        return safe

    def _quarantine(self, payload: bytes, extension: str, *, digest: str) -> str:
        if not self.quarantine_enabled or not payload:
            return ""
        root = str(self.quarantine_dir or "").strip()
        if not root:
            return ""

        path = os.path.abspath(os.path.expanduser(root))
        try:
            os.makedirs(path, mode=0o700, exist_ok=True)
            try:
                os.chmod(path, 0o700)
            except OSError:
                pass
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            suffix = self._safe_quarantine_extension(extension)
            base = digest[:16] if digest else "payload"
            file_name = f"{timestamp}_{base}{suffix}"
            out_path = os.path.join(path, file_name)
            with open(out_path, "wb") as handle:
                handle.write(payload)
            try:
                os.chmod(out_path, 0o600)
            except OSError:
                pass
            return out_path
        except Exception:
            return ""

    def _audit(
        self,
        *,
        result: str,
        source_name: str,
        extension: str,
        size_bytes: int,
        sha256: str,
        reason: str,
        quarantine_path: str,
    ) -> None:
        if not self.audit_log_path:
            return
        entry = {
            "timestamp_utc": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "result": str(result or "").strip().lower(),
            "source_name": os.path.basename(str(source_name or "").strip() or "document"),
            "extension": str(extension or "").strip().lower(),
            "size_bytes": int(size_bytes),
            "sha256": str(sha256 or "").strip(),
            "reason": str(reason or "").strip(),
            "quarantine_path": str(quarantine_path or "").strip(),
        }

        log_path = os.path.abspath(os.path.expanduser(self.audit_log_path))
        log_dir = os.path.dirname(log_path) or "."
        try:
            os.makedirs(log_dir, mode=0o700, exist_ok=True)
            previous_hash = self._read_last_audit_hash(log_path)
            entry["previous_hash"] = previous_hash
            canonical = json.dumps(entry, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            entry["entry_hash"] = hashlib.sha256(f"{previous_hash}|{canonical}".encode("utf-8")).hexdigest()
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
            try:
                os.chmod(log_path, 0o600)
            except OSError:
                pass
        except Exception:
            return

    def _read_last_audit_hash(self, log_path: str) -> str:
        if not os.path.exists(log_path):
            return "0" * 64
        try:
            with open(log_path, "rb") as handle:
                content = handle.read()
            lines = content.decode("utf-8", errors="replace").splitlines()
            for raw in reversed(lines):
                line = raw.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                value = str(payload.get("entry_hash", "")).strip().lower()
                if len(value) == 64 and all(ch in "0123456789abcdef" for ch in value):
                    return value
        except Exception:
            return "0" * 64
        return "0" * 64

    def _size_error_message(self, size_bytes: int) -> str:
        max_mb = int(self.max_input_bytes / (1024 * 1024))
        got_mb = float(size_bytes) / float(1024 * 1024)
        return f"Document is too large ({got_mb:.1f} MB). Maximum allowed is {max_mb} MB."
