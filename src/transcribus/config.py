# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Configuration loaded from environment / .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Secrets come from env or a local .env file."""

    model_config = SettingsConfigDict(
        env_prefix="TRANSKRIBUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    user: str = ""
    password: str = ""
    base_url: str = "https://transkribus.eu/TrpServer/rest"

    # Optional defaults for pipeline runs
    coll_id: int | None = None
    model_id: int | None = None
    engine: str = "auto"

    # FTP bulk upload (host fixed by Transkribus; creds default to the login).
    ftp_host: str = "transkribus.eu"
    ftp_user: str | None = None
    ftp_password: str | None = None

    def ftp_credentials(self) -> tuple[str, str, str]:
        """(host, user, password) for FTP — falls back to the readcoop login."""
        return (
            self.ftp_host,
            self.ftp_user or self.user,
            self.ftp_password or self.password,
        )

    def require_credentials(self) -> None:
        if not self.user or not self.password:
            raise RuntimeError(
                "Missing Transkribus credentials. Set TRANSKRIBUS_USER and "
                "TRANSKRIBUS_PASSWORD (env or .env)."
            )


def load_settings() -> Settings:
    return Settings()
