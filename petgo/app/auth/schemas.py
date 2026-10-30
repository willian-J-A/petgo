"""Schemas de validação para autenticação (Marshmallow)."""
from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate, validates


class RegisterSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=2, max=120))
    email = fields.Email(required=True)
    password = fields.Str(
        required=True,
        validate=validate.Length(min=8, max=128),
        load_only=True,
    )
    city = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    state = fields.Str(required=True, validate=validate.Length(equal=2))

    @validates("state")
    def validate_state(self, value):
        br_states = {
            "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
            "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
            "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
        }
        if value.upper() not in br_states:
            raise ValidationError("UF inválida.")
        return value.upper()


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)


class ForgotPasswordSchema(Schema):
    email = fields.Email(required=True)


class ResetPasswordSchema(Schema):
    token = fields.Str(required=True)
    password = fields.Str(
        required=True, validate=validate.Length(min=8, max=128), load_only=True
    )


class UpdateProfileSchema(Schema):
    phone = fields.Str(allow_none=True, validate=validate.Length(max=20))
    interested_in_adoption = fields.Bool()
    species_preferences = fields.List(fields.Str())
    city = fields.Str(validate=validate.Length(min=2, max=100))
    state = fields.Str(validate=validate.Length(equal=2))
    email_opt_in = fields.Bool()
    all_locations = fields.Bool()
