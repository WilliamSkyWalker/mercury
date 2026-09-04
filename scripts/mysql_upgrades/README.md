# MySQL Schema Upgrades

Mercury database schemas are maintained with hand-written SQL. Do not use
`manage.py makemigrations` or `manage.py migrate`.

- Use `scripts/mercury_mysql_schema.sql` only when initializing a new database.
- Add one idempotent upgrade file for every change to an existing table.
- Name files `YYYYMMDD_NNN_description.sql` so deployment order is explicit.
- Use `ALTER TABLE`, `CREATE INDEX`, or other targeted statements; do not copy
  the full schema into an upgrade file.
- Update `scripts/mercury_mysql_schema.sql` in the same change so fresh
  databases include the final structure.
- Back up the target database and test the upgrade against a copy before
  production execution.
