"""Point d'entrée WSGI pour les serveurs de production (Gunicorn) :

    gunicorn -c gunicorn.conf.py wsgi:app
"""
from app import create_app
from app.tasks import make_celery

app = create_app()
celery = make_celery(app)

if __name__ == "__main__":
    app.run()
