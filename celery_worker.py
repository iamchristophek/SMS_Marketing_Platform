"""Point d'entrée pour le worker Celery (envoi asynchrone des SMS) :

    celery -A celery_worker.celery worker --loglevel=info

Et pour le scheduler (dispatch des campagnes planifiées) :

    celery -A celery_worker.celery beat --loglevel=info
"""
from app import create_app
from app.tasks import make_celery
import app.tasks.sms_tasks  # noqa: F401 - enregistre les tâches auprès de Celery
import app.tasks.payment_tasks  # noqa: F401 - enregistre les tâches auprès de Celery

flask_app = create_app()
celery = make_celery(flask_app)
