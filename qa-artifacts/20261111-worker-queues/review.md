# Separate OCR and maintenance queues

New uploads and retries use the `celery` queue. Rule rechecks and backups use `maintenance`, consumed by a separate worker. The OCR worker writes the media volume; the maintenance worker reads media and writes only the backup volume. Both local and Portainer Compose files include the new worker.

The prior six-worker browser run timed out on two late mobile steps while a reclassification job used the only worker for about 31 seconds. Both steps passed when rerun alone after the backlog cleared. This change removes that queue head-of-line delay; it does not remove CPU or database contention between concurrent jobs.

Verification on 11 November 2026: 40 API tests passed, Django reported no pending migrations, and both Compose files passed `docker compose config -q`. Celery's live `active_queues` reported one worker on `celery` and one on `maintenance`. A no-change `reclassify_tag_candidates` task was received and completed by the maintenance worker. The desktop capture/OCR/search/physical-copy browser journey passed against the two-worker stack in 8.7 seconds. NAS memory and real-device behavior remain release gates.
