#!/bin/bash

python3 destroy_db_containers.py

python3 start_db_containers.py --rebuild --mariadb-version 12.0

# Load schema
mariadb -h localhost -u root -prootpassword testdb < sample_mariadb_schema.sql

# Load data (1000 rows per table)
mariadb -h localhost -u root -prootpassword testdb < sample_mariadb_data.sql

python3 setup_migration.py \
  --mariadb-database testdb \
  --scylla-ks target_ks

python3 modify_sample_mariadb_data.py \
  --mariadb-database testdb \
  --scylla-ks target_ks
