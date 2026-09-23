"""Configuration Celery. `make_celery` lie l'application Flask au worker
Celery afin que les tâches disposent d'un contexte applicatif (accès à la
base de données, à la config...).

`make_celery` est appelé par l'application factory (create_app) : la config
Celery (broker, mode eager en dev/test) suit donc toujours la config Flask,
quel que soit le point d'entrée (wsgi.py, celery_worker.py, `flask run`,
tests). L'appel est idempotent.
"""
from celery import Celery
from flask import has_app_context

celery_app = Celery(__name__)

# Application Flask liée au worker, mise à jour à chaque appel de
# make_celery (une nouvelle application est créée pour chaque test).
_flask_app = None


class ContextTask(celery_app.Task):
    abstract = True

    def __call__(self, *args, **kwargs):
        # Exécution eager depuis une requête/un test : un contexte applicatif
        # existe déjà, on le réutilise (même session de base de données).
        if has_app_context() or _flask_app is None:
            return self.run(*args, **kwargs)
        with _flask_app.app_context():
            return self.run(*args, **kwargs)


celery_app.Task = ContextTask


def make_celery(app):
    global _flask_app
    _flask_app = app
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
        },
    )
    celery_app.set_default()
    return celery_app
