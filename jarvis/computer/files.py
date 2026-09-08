import os
from pathlib import Path


class FileWorkspace:
    SENSITIVE_NAMES = {
        ".env",
        ".git-credentials",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "credentials.json",
        "id_dsa",
        "id_ed25519",
        "id_rsa",
    }
    SENSITIVE_SUFFIXES = {".key", ".pem", ".pfx", ".p12"}

    def _path(self, raw_path: str) -> Path:
        if not raw_path.strip():
            raise ValueError("A file or folder path is required")
        path = Path(raw_path).expanduser()
        if path.is_symlink():
            raise PermissionError("JARVIS will not access symbolic links")
        return path.resolve()

    def _check_sensitive(self, path: Path):
        if (
            path.name.lower() in self.SENSITIVE_NAMES
            or path.suffix.lower() in self.SENSITIVE_SUFFIXES
        ):
            raise PermissionError("JARVIS will not access credential or key files")

    def list_directory(self, raw_path: str) -> str:
        path = self._path(raw_path)
        if not path.is_dir():
            raise FileNotFoundError(f"Directory not found: {path}")
        entries = sorted(
            path.iterdir(),
            key=lambda entry: (not entry.is_dir(), entry.name.lower()),
        )
        visible = entries[:150]
        lines = [
            f"{'[folder]' if entry.is_dir() else '[file]'} {entry.name}"
            for entry in visible
        ]
        if len(entries) > len(visible):
            lines.append(f"... and {len(entries) - len(visible)} more")
        return "\n".join(lines) or "The directory is empty."

    def read_text(self, raw_path: str) -> str:
        path = self._path(raw_path)
        self._check_sensitive(path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        if path.stat().st_size > 50_000:
            raise ValueError("Text files larger than 50 KB are not read into the model")
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("The selected file is not UTF-8 text") from exc

    def write_text(
        self,
        raw_path: str,
        content: str,
        overwrite: bool = False,
    ) -> str:
        path = self._path(raw_path)
        self._check_sensitive(path)
        if path.exists() and not overwrite:
            raise FileExistsError(
                f"{path} already exists; explicit overwrite approval is required"
            )
        if not path.parent.is_dir():
            raise FileNotFoundError(f"Parent directory not found: {path.parent}")
        path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {path}."

    def create_folder(self, raw_path: str) -> str:
        path = self._path(raw_path)
        path.mkdir(parents=False, exist_ok=False)
        return f"Created folder {path}."

    def rename(self, raw_source: str, raw_destination: str) -> str:
        source = self._path(raw_source)
        destination = self._path(raw_destination)
        self._check_sensitive(source)
        self._check_sensitive(destination)
        if not source.exists():
            raise FileNotFoundError(f"Path not found: {source}")
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}")
        if not destination.parent.is_dir():
            raise FileNotFoundError(
                f"Destination folder not found: {destination.parent}"
            )
        source.rename(destination)
        return f"Renamed {source} to {destination}."

    def open_path(self, raw_path: str) -> str:
        path = self._path(raw_path)
        self._check_sensitive(path)
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if os.name != "nt":
            raise RuntimeError("Opening files is available only on Windows")
        os.startfile(path)
        return f"Opened {path}."
