"""Background processing: Dramatiq actors fed by the transactional-outbox relay.

Run `python -m worker` next to the API when Redis is configured. Without Redis the API starts the same
relay and actors in-process (see `worker.runtime`), so the lite demo needs no extra services."""
