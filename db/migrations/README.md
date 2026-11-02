# Migrations

Ordered, idempotent SQL. File names are `NNN_description.sql`, applied in order.
`db/init/` runs once on first database creation; migrations run against existing
databases. Keep migrations backward safe so rollbacks do not break older images.
