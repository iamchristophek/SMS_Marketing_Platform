#!/bin/sh
# Sauvegarde PostgreSQL compressée, horodatée, avec rotation.
# Lancé chaque jour par le service `backup` de docker-compose ; utilisable
# à la main : docker compose run --rm backup /bin/sh /backup.sh
# Restauration : gunzip -c backups/baoryx-AAAAMMJJ-HHMM.sql.gz | docker compose exec -T db psql -U baoryx baoryx
set -eu
dir=/backups
file="$dir/baoryx-$(date +%Y%m%d-%H%M).sql.gz"
pg_dump --no-owner --clean --if-exists | gzip > "$file.tmp"
mv "$file.tmp" "$file"
find "$dir" -name 'baoryx-*.sql.gz' -mtime +"${BACKUP_KEEP_DAYS:-14}" -delete
echo "Sauvegarde OK : $file ($(du -h "$file" | cut -f1))"
