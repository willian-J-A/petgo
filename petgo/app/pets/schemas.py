"""Schemas de validação para pets."""
from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

SPECIES = {"DOG", "CAT", "OTHER"}
HELP_TYPES = {"RESCUE", "ADOPTION", "TREATMENT", "FOSTER"}
SIZES = {"SMALL", "MEDIUM", "LARGE"}
SEXES = {"M", "F"}


class CreatePetSchema(Schema):
    species = fields.Str(required=True)
    help_type = fields.Str(required=True)
    description = fields.Str(required=True, validate=validate.Length(min=10, max=2000))
    city = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    state = fields.Str(required=True, validate=validate.Length(equal=2))
    media_ids = fields.List(fields.Int(), required=True, validate=validate.Length(min=1, max=5))

    # Campos opcionais
    size = fields.Str(load_default=None)
    sex = fields.Str(load_default=None)
    age_months = fields.Int(load_default=None, validate=validate.Range(min=0, max=360))
    latitude = fields.Float(load_default=None)
    longitude = fields.Float(load_default=None)

    # Risco opcional na publicação
    risk_reported = fields.Bool(load_default=False)
    risk_description = fields.Str(load_default=None)

    # ONG responsável opcional
    ngo_id = fields.Int(load_default=None)

    @validates_schema
    def validate_enums(self, data, **kwargs):
        errors = {}
        if data.get("species") not in SPECIES:
            errors["species"] = [f"Deve ser um de: {SPECIES}"]
        if data.get("help_type") not in HELP_TYPES:
            errors["help_type"] = [f"Deve ser um de: {HELP_TYPES}"]
        if data.get("size") and data["size"] not in SIZES:
            errors["size"] = [f"Deve ser um de: {SIZES}"]
        if data.get("sex") and data["sex"] not in SEXES:
            errors["sex"] = [f"Deve ser um de: {SEXES}"]
        if data.get("help_type") == "RESCUE" and (
            data.get("latitude") is None or data.get("longitude") is None
        ):
            errors["latitude"] = ["Coordenadas obrigatórias para tipo RESCUE."]
        if errors:
            raise ValidationError(errors)


class UpdatePetSchema(Schema):
    description = fields.Str(validate=validate.Length(min=10, max=2000))
    city = fields.Str(validate=validate.Length(min=2, max=100))
    state = fields.Str(validate=validate.Length(equal=2))
    size = fields.Str()
    sex = fields.Str()
    age_months = fields.Int(validate=validate.Range(min=0, max=360))
    # Campos proibidos: status, risk decidido, publicador, pontos, ngo responsável, adotante


class PetFilterSchema(Schema):
    species = fields.Str(load_default=None)
    size = fields.Str(load_default=None)
    sex = fields.Str(load_default=None)
    city = fields.Str(load_default=None)
    state = fields.Str(load_default=None)
    help_type = fields.Str(load_default=None)
    risk_validated = fields.Bool(load_default=None)
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
