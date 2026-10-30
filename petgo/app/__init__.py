"""PetGo — Application Factory."""
from __future__ import annotations

import logging
import os

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name: str | None = None) -> Flask:
    """Cria e configura a aplicação Flask."""
    app = Flask(__name__, instance_relative_config=False)

    # Configuração
    _load_config(app, config_name)

    # Logging sanitizado (sem dados sensíveis)
    _configure_logging(app)

    # Extensões
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para continuar."
    login_manager.login_message_category = "warning"

    # Blueprints
    _register_blueprints(app)

    # Handlers de erro centralizados
    from app.errors import register_error_handlers
    register_error_handlers(app)

    # Importar modelos para que o Alembic os detecte
    with app.app_context():
        from app import models  # noqa: F401

    return app


def _load_config(app: Flask, config_name: str | None) -> None:
    env = config_name or os.getenv("APP_ENV", "development")

    from app.config import configs

    app.config.from_object(configs[env])

    # Variáveis sensíveis só via ambiente — nunca em arquivo versionado
    for key in ("SECRET_KEY", "DATABASE_URL", "VOUCHER_ENCRYPTION_KEY"):
        value = os.getenv(key)
        if value:
            app.config[key] = value


def _configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Suprimir SQLAlchemy em produção
    if not app.debug:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _register_blueprints(app: Flask) -> None:
    from app.auth.routes import bp as auth_bp
    from app.health import bp as health_bp
    from app.web.routes import bp as web_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/v1")
    app.register_blueprint(web_bp)  # rotas Jinja2 sem prefixo

    # Blueprints adicionais
    from app.organizations.routes import bp as org_bp
    from app.pets.routes import bp as pets_bp
    from app.rescues.routes import bp as rescues_bp
    from app.adoptions.routes import bp as adoptions_bp
    from app.gamification.routes import bp as gamification_bp
    from app.rewards.routes import bp as rewards_bp
    from app.admin.routes import bp as admin_bp

    app.register_blueprint(org_bp, url_prefix="/api/v1")
    app.register_blueprint(pets_bp, url_prefix="/api/v1")
    app.register_blueprint(rescues_bp, url_prefix="/api/v1")
    app.register_blueprint(adoptions_bp, url_prefix="/api/v1")
    app.register_blueprint(gamification_bp, url_prefix="/api/v1")
    app.register_blueprint(rewards_bp, url_prefix="/api/v1")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
