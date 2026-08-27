from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class CreditPackage(db.Model):
    """Offre de recharge de crédits SMS, tarifée en Francs CFA (XOF)."""

    __tablename__ = "credit_packages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    credits = db.Column(db.Integer, nullable=False)
    price_xof = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    @property
    def price_per_sms(self):
        if not self.credits:
            return 0
        return round(self.price_xof / self.credits, 2)


class CreditTransaction(db.Model):
    """Journal comptable des crédits (source de vérité). Le solde d'une
    Business (`credit_balance`) est une valeur mise en cache, toujours
    recalculable à partir de la somme des transactions."""

    __tablename__ = "credit_transactions"

    TYPE_PURCHASE = "purchase"
    TYPE_CONSUMPTION = "consumption"
    TYPE_REFUND = "refund"
    TYPE_BONUS = "bonus"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)

    type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # positif = crédit, négatif = débit
    balance_after = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255))

    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    business = db.relationship("Business", back_populates="credit_transactions")

    def __repr__(self):
        return f"<CreditTransaction {self.type} {self.amount}>"


class Payment(db.Model):
    """Tentative de paiement (Mobile Money / carte) pour l'achat d'un pack
    de crédits."""

    __tablename__ = "payments"

    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    package_id = db.Column(db.Integer, db.ForeignKey("credit_packages.id"), nullable=False)

    amount_xof = db.Column(db.Integer, nullable=False)
    credits = db.Column(db.Integer, nullable=False)
    provider = db.Column(db.String(30), nullable=False)  # orange_money, mtn_momo, wave, manual...
    provider_reference = db.Column(db.String(120), unique=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True))

    business = db.relationship("Business", back_populates="payments")
    package = db.relationship("CreditPackage")

    def __repr__(self):
        return f"<Payment {self.provider} {self.amount_xof}XOF {self.status}>"
