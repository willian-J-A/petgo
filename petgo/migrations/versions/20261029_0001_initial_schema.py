"""Initial schema — todas as tabelas PetGo MVP.

Revision ID: 0001
Revises:
Create Date: 2026-10-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email_normalized", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("interested_in_adoption", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("species_preferences", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("email_opt_in", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("all_locations", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_normalized", name="uq_users_email"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # auth_tokens
    # ------------------------------------------------------------------
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_hash"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # ngos
    # ------------------------------------------------------------------
    op.create_table(
        "ngos",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("cnpj_normalized", sa.String(14), nullable=False),
        sa.Column("contact_email", sa.String(254), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("verification_status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("verified_by", sa.BigInteger(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cnpj_normalized", name="uq_ngos_cnpj"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # ngo_members
    # ------------------------------------------------------------------
    op.create_table(
        "ngo_members",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ngo_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("role", sa.String(32), nullable=False, server_default="MEMBER"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ngo_id"], ["ngos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ngo_id", "user_id", name="uq_ngo_member"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # pets
    # ------------------------------------------------------------------
    op.create_table(
        "pets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("publisher_user_id", sa.BigInteger(), nullable=False),
        sa.Column("responsible_user_id", sa.BigInteger(), nullable=True),
        sa.Column("responsible_ngo_id", sa.BigInteger(), nullable=True),
        sa.Column("species", sa.String(16), nullable=False),
        sa.Column("size", sa.String(16), nullable=True),
        sa.Column("sex", sa.String(8), nullable=True),
        sa.Column("age_months", sa.Integer(), nullable=True),
        sa.Column("help_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="NEEDS_RESCUE"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("private_location", sa.JSON(), nullable=True),
        sa.Column("risk_status", sa.String(16), nullable=False, server_default="NONE"),
        sa.Column("risk_details", sa.Text(), nullable=True),
        sa.Column("risk_decided_by", sa.BigInteger(), nullable=True),
        sa.Column("risk_decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rescued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("adopted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("adopter_user_id", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publisher_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["responsible_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["responsible_ngo_id"], ["ngos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["risk_decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["adopter_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_pets_status_city_state_species", "pets",
                    ["status", "city", "state", "species"])
    op.create_index("ix_pets_risk_status", "pets", ["risk_status", "status"])

    # ------------------------------------------------------------------
    # media
    # ------------------------------------------------------------------
    op.create_table(
        "media",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pet_id", sa.BigInteger(), nullable=True),
        sa.Column("ngo_id", sa.BigInteger(), nullable=True),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="PRIVATE"),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pet_id"], ["pets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ngo_id"], ["ngos.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_media_storage_key"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # pet_events
    # ------------------------------------------------------------------
    op.create_table(
        "pet_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pet_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("acting_ngo_id", sa.BigInteger(), nullable=True),
        sa.Column("from_status", sa.String(24), nullable=True),
        sa.Column("to_status", sa.String(24), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_media_id", sa.BigInteger(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pet_id"], ["pets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["acting_ngo_id"], ["ngos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["evidence_media_id"], ["media.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # rescues
    # ------------------------------------------------------------------
    op.create_table(
        "rescues",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pet_id", sa.BigInteger(), nullable=False),
        sa.Column("ngo_id", sa.BigInteger(), nullable=False),
        sa.Column("executor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="ASSUMED"),
        sa.Column("evidence_media_id", sa.BigInteger(), nullable=True),
        sa.Column("confirmed_by", sa.BigInteger(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pet_id"], ["pets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ngo_id"], ["ngos.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["executor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_media_id"], ["media.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    # Unicidade de atendimento ativo: um ASSUMED ou PENDING_CONFIRMATION por pet
    # MySQL permite múltiplos NULL em índices únicos.
    op.execute(
        """
        ALTER TABLE rescues
        ADD COLUMN active_pet_id BIGINT
            GENERATED ALWAYS AS (
                CASE WHEN status IN ('ASSUMED','PENDING_CONFIRMATION') THEN pet_id ELSE NULL END
            ) STORED,
        ADD UNIQUE INDEX uq_rescues_active_pet (active_pet_id)
        """
    )

    # ------------------------------------------------------------------
    # wallets
    # ------------------------------------------------------------------
    op.create_table(
        "wallets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("ngo_id", sa.BigInteger(), nullable=True),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ngo_id"], ["ngos.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_wallets_user"),
        sa.UniqueConstraint("ngo_id", name="uq_wallets_ngo"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # point_awards
    # ------------------------------------------------------------------
    op.create_table(
        "point_awards",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pet_id", sa.BigInteger(), nullable=False),
        sa.Column("phase", sa.String(16), nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=True),
        sa.Column("risk_snapshot", sa.String(16), nullable=True),
        sa.Column("policy_version", sa.String(16), nullable=False, server_default="v1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="SETTLED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pet_id"], ["pets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["event_id"], ["pet_events.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pet_id", "phase", name="uq_point_award_pet_phase"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # point_entries
    # ------------------------------------------------------------------
    op.create_table(
        "point_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("wallet_id", sa.BigInteger(), nullable=False),
        sa.Column("award_id", sa.BigInteger(), nullable=True),
        sa.Column("redemption_id", sa.BigInteger(), nullable=True),
        sa.Column("correction_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("entry_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["award_id"], ["point_awards.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_key", name="uq_point_entries_key"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_point_entries_wallet_id", "point_entries", ["wallet_id", "id"])

    # ------------------------------------------------------------------
    # partners
    # ------------------------------------------------------------------
    op.create_table(
        "partners",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("contact_email", sa.String(254), nullable=False),
        sa.Column("terms", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # partner_members
    # ------------------------------------------------------------------
    op.create_table(
        "partner_members",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("partner_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("partner_id", "user_id", name="uq_partner_member"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # rewards
    # ------------------------------------------------------------------
    op.create_table(
        "rewards",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("partner_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cost_points", sa.Integer(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voucher_lifetime_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("eligibility", sa.String(16), nullable=False, server_default="BOTH"),
        sa.Column("fulfillment_terms", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # redemptions
    # ------------------------------------------------------------------
    op.create_table(
        "redemptions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("wallet_id", sa.BigInteger(), nullable=False),
        sa.Column("reward_id", sa.BigInteger(), nullable=False),
        sa.Column("cost_snapshot", sa.Integer(), nullable=False),
        sa.Column("terms_snapshot", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ISSUED"),
        sa.Column("voucher_hash", sa.String(128), nullable=False),
        sa.Column("voucher_ciphertext", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reward_id"], ["rewards.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["consumed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("voucher_hash", name="uq_redemptions_voucher_hash"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_redemptions_status_expires", "redemptions", ["status", "expires_at"])

    # ------------------------------------------------------------------
    # adoption_requests
    # ------------------------------------------------------------------
    op.create_table(
        "adoption_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pet_id", sa.BigInteger(), nullable=False),
        sa.Column("applicant_user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="SENT"),
        sa.Column("origin_status", sa.String(24), nullable=True),
        sa.Column("participating_ngo_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("delivery_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("receipt_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pet_id"], ["pets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["applicant_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["participating_ngo_id"], ["ngos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    # Unicidade de pedido ativo por (pet, solicitante)
    op.execute(
        """
        ALTER TABLE adoption_requests
        ADD COLUMN active_applicant_id BIGINT
            GENERATED ALWAYS AS (
                CASE WHEN status IN ('SENT','UNDER_REVIEW','APPROVED')
                     THEN applicant_user_id ELSE NULL END
            ) STORED,
        ADD UNIQUE INDEX uq_adoption_active_applicant (pet_id, active_applicant_id)
        """
    )
    # Reserva única: apenas um APPROVED ou COMPLETED por pet
    op.execute(
        """
        ALTER TABLE adoption_requests
        ADD COLUMN active_reservation_pet BIGINT
            GENERATED ALWAYS AS (
                CASE WHEN status IN ('APPROVED','COMPLETED')
                     THEN pet_id ELSE NULL END
            ) STORED,
        ADD UNIQUE INDEX uq_adoption_reservation (active_reservation_pet)
        """
    )

    # ------------------------------------------------------------------
    # outbox_events
    # ------------------------------------------------------------------
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_outbox_event_key"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # email_deliveries
    # ------------------------------------------------------------------
    op.create_table(
        "email_deliveries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_email_snapshot", sa.String(254), nullable=False),
        sa.Column("template", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_id", sa.String(128), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sanitized_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["outbox_events.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "user_id", "template", name="uq_email_delivery"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_email_deliveries_status_next", "email_deliveries",
        ["status", "next_attempt_at"]
    )

    # ------------------------------------------------------------------
    # audit_logs
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("sanitized_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ------------------------------------------------------------------
    # idempotency_keys
    # ------------------------------------------------------------------
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "actor_user_id", "operation", "key", name="uq_idempotency"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # FK de point_entries.redemption_id adicionada após criação de redemptions
    op.create_foreign_key(
        "fk_point_entries_redemption",
        "point_entries",
        "redemptions",
        ["redemption_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Ordem reversa de dependências
    op.drop_constraint("fk_point_entries_redemption", "point_entries", type_="foreignkey")
    op.drop_table("idempotency_keys")
    op.drop_table("audit_logs")
    op.drop_table("email_deliveries")
    op.drop_table("outbox_events")
    op.drop_table("adoption_requests")
    op.drop_table("redemptions")
    op.drop_table("rewards")
    op.drop_table("partner_members")
    op.drop_table("partners")
    op.drop_table("point_entries")
    op.drop_table("point_awards")
    op.drop_table("wallets")
    op.drop_table("rescues")
    op.drop_table("pet_events")
    op.drop_table("media")
    op.drop_table("pets")
    op.drop_table("ngo_members")
    op.drop_table("ngos")
    op.drop_table("auth_tokens")
    op.drop_table("users")
