"""Configuration Celery. `make_celery` lie l'application Flask au worker
Celery afin que les tâches disposent d'un contexte applicatif (accès à la
base de données, à la config...).
"""
from celery import Celery

celery_app = Celery(__name__)


def make_celery(app):
    celery_app.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        task_always_eager=app.config.get("CELERY_TASK_ALWAYS_EAGER", False),
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        beat_schedule={
            "dispatch-scheduled-campaigns": {
                "task": "app.tasks.sms_tasks.dispatch_scheduled_campaigns",
                "schedule": 60.0,  # vérifie chaque minute les campagnes planifiées
            },
            "reconcile-pending-payments": {
                "task": "app.tasks.payment_tasks.reconcile_pending_payments",
                "schedule": 300.0,  # rattrape les paiements Mobile Money sans webhook toutes les 5 min
            },
        },
    )

    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
    celery_app.set_default()
    return celery_app
