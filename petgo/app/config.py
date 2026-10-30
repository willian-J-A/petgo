"""Configurações por ambiente."""
from __future__ import annotations

import os


class BaseConfig:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key")
    DEBUG = False
    TESTING = False

    # Banco
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "mysql+pymysql://petgo:petgo@127.0.0.1:3306/petgo"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    # Flask-WTF / CSRF
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hora

    # Upload
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB por arquivo
    ALLOWED_MEDIA_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
    ALLOWED_MEDIA_MIMETYPES = {"image/jpeg", "image/png", "image/webp"}
    MAX_MEDIA_PER_PET = 5

    # AWS
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    MEDIA_BUCKET = os.getenv("MEDIA_BUCKET", "")
    BACKUP_BUCKET = os.getenv("BACKUP_BUCKET", "")
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5000")

    # E-mail
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@petgo.local")

    # Voucher
    VOUCHER_ENCRYPTION_KEY = os.getenv("VOUCHER_ENCRYPTION_KEY", "")

    # Idempotência
    IDEMPOTENCY_KEY_TTL_DAYS = 7

    # Rate limiting (referência; implementação no decorator)
    LOGIN_MAX_ATTEMPTS = 10
    LOGIN_WINDOW_SECONDS = 300


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "mysql+pymysql://petgo:petgo@127.0.0.1:3306/petgo_dev"
    )


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    # Testes transacionais rodam em MySQL real isolado, não SQLite
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "mysql+pymysql://petgo:petgo@127.0.0.1:3306/petgo_test"
    )
    WTF_CSRF_ENABLED = False
    # SMTP mock em testes
    SMTP_HOST = ""


class ProductionConfig(BaseConfig):
    DEBUG = False

    @classmethod
    def validate(cls) -> None:
        """Falha rápido se segredos obrigatórios faltam em produção."""
        required = ["SECRET_KEY", "DATABASE_URL", "VOUCHER_ENCRYPTION_KEY"]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise RuntimeError(
                f"Variáveis de ambiente obrigatórias ausentes: {missing}"
            )


configs: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
