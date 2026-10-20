from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class Feedback(db.Model):
    """Avis laissé par un utilisateur depuis l'application (bêta)."""

    __tablename__ = "feedbacks"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rating = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text, nullable=False)
    page = db.Column(db.String(200))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    business = db.relationship("Business")
    user = db.relationship("User")
