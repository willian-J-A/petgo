"""Importa todos os modelos para que o Alembic os detecte.

Cada módulo define seus próprios modelos herdando de db.Model.
Este arquivo serve apenas de ponto de entrada para o autogenerate
do Flask-Migrate.
"""
from __future__ import annotations

# Os modelos serão importados aqui conforme cada task for implementada.
# Por enquanto, importa o modelo de usuário base (Task 3).
try:
    from app.auth.models import User, AuthToken  # noqa: F401
except ImportError:
    pass

try:
    from app.organizations.models import Ngo, NgoMember  # noqa: F401
except ImportError:
    pass

try:
    from app.pets.models import Pet, Media, PetEvent  # noqa: F401
except ImportError:
    pass

try:
    from app.rescues.models import Rescue  # noqa: F401
except ImportError:
    pass

try:
    from app.adoptions.models import AdoptionRequest  # noqa: F401
except ImportError:
    pass

try:
    from app.gamification.models import (  # noqa: F401
        Wallet,
        PointAward,
        PointEntry,
    )
except ImportError:
    pass

try:
    from app.rewards.models import (  # noqa: F401
        Partner,
        PartnerMember,
        Reward,
        Redemption,
    )
except ImportError:
    pass

try:
    from app.notifications.models import OutboxEvent, EmailDelivery  # noqa: F401
except ImportError:
    pass

try:
    from app.admin.models import AuditLog, IdempotencyKey  # noqa: F401
except ImportError:
    pass
