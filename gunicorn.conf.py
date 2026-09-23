import multiprocessing
import os

bind = "0.0.0.0:8000"
# Dans un conteneur, cpu_count() renvoie les CPU de la machine hôte (souvent
# 16 ou 64) : 2×CPU+1 lancerait des dizaines de workers et saturerait la
# mémoire d'un petit serveur. Plafond par défaut à 4, ajustable avec
# WEB_CONCURRENCY (compter ~100 Mo de RAM par worker).
workers = int(os.environ.get("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 4)))
worker_class = "sync"
timeout = 30
accesslog = "-"
errorlog = "-"
