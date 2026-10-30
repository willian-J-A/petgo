"""Tratamento centralizado de erros — sem stack trace para o cliente."""
from __future__ import annotations

import uuid

from flask import jsonify, request
from werkzeug.exceptions import HTTPException


def _error_response(code: str, message: str, fields: dict | None = None, status: int = 400):
    return (
        jsonify(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "fields": fields or {},
                    "request_id": str(uuid.uuid4()),
                }
            }
        ),
        status,
    )


class DomainError(Exception):
    """Base para erros de domínio com código HTTP."""
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return _error_response("BAD_REQUEST", "Requisição inválida.", status=400)

    @app.errorhandler(401)
    def unauthorized(e):
        return _error_response("UNAUTHORIZED", "Autenticação necessária.", status=401)

    @app.errorhandler(403)
    def forbidden(e):
        return _error_response("FORBIDDEN", "Acesso negado.", status=403)

    @app.errorhandler(404)
    def not_found(e):
        return _error_response("NOT_FOUND", "Recurso não encontrado.", status=404)

    @app.errorhandler(409)
    def conflict(e):
        return _error_response("CONFLICT", str(e), status=409)

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return _error_response("FILE_TOO_LARGE", "Arquivo excede o limite.", status=413)

    @app.errorhandler(422)
    def unprocessable(e):
        return _error_response("VALIDATION_ERROR", "Campos inválidos.", status=422)

    @app.errorhandler(429)
    def rate_limit(e):
        return _error_response("RATE_LIMITED", "Muitas tentativas. Tente novamente em instantes.", status=429)

    @app.errorhandler(HTTPException)
    def http_exception(e):
        return _error_response(e.name.upper().replace(" ", "_"), e.description, status=e.code)

    @app.errorhandler(Exception)
    def unhandled(e):
        # Trata erros de domínio com atributo .status
        if hasattr(e, "status") and hasattr(e, "code") and hasattr(e, "message"):
            return _error_response(e.code, e.message, status=e.status)
        app.logger.exception("Erro não tratado")
        return _error_response("INTERNAL_ERROR", "Erro interno.", status=500)
