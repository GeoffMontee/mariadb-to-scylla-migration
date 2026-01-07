# Getting Started with MariaDB to ScyllaDB Migration

This document provides quick instructions for getting started with the MariaDB to ScyllaDB migration toolkit.

## Before You Begin

### Required Storage Engine Files

This repository needs the MariaDB ScyllaDB storage engine source files. You must copy the following files from the [mariadb-scylla-storage-engine](https://github.com/GeoffMontee/mariadb-scylla-storage-engine) repository to this directory:

```bash
# Clone the storage engine repository
git clone https://github.com/GeoffMontee/mariadb-scylla-storage-engine.git /tmp/storage-engine

# Copy required files to this directory
cp /tmp/storage-engine/ha_scylla.* .
cp /tmp/storage-engine/scylla_connection.* .
cp /tmp/storage-engine/scylla_types.* .
cp /tmp/storage-engine/scylla_query.* .
cp /tmp/storage-engine/plugin.cmake .
cp /tmp/storage-engine/CMakeLists.txt .
```

### Install Python Dependencies

```bash
pip install -r requirements.txt
```

## Quick Start (5 Steps)

### 1. Copy Storage Engine Files
See "Before You Begin" section above.

### 2. Start Containers
```bash
python3 start_db_containers.py
```

**Note:** The first run will build MariaDB from source (15-30 minutes). Subsequent runs will be much faster.

### 3. Load Sample Data
```bash
mariadb -h localhost -u root -prootpassword testdb < sample_mariadb_schema.sql
mariadb -h localhost -u root -prootpassword testdb < sample_mariadb_data.sql
```

### 4. Setup Migration
```bash
python3 setup_migration.py \
  --mariadb-database testdb \
  --mariadb-scylla-database scylla_db \
  --scylla-ks target_ks
```

This will:
- Create a separate `scylla_db` database for ScyllaDB-backed tables
- Create matching tables in ScyllaDB
- Create triggers for replication
- Migrate existing data

### 5. Test Replication
```bash
python3 modify_sample_mariadb_data.py --mariadb-database testdb --scylla-ks target_ks
```

## Alternative: Run Everything at Once

```bash
chmod +x reset.sh
./reset.sh
```

The `reset.sh` script will:
1. Destroy any existing containers
2. Start fresh containers
3. Load sample schema and data
4. Setup migration
5. Test replication

## Verifying the Setup

### Check MariaDB is Running
```bash
mariadb -h localhost -u root -prootpassword testdb -e "SHOW ENGINES;"
```

You should see `SCYLLA` in the list of engines.

### Check ScyllaDB is Running
```bash
docker exec -it scylladb-migration-target cqlsh -e "DESCRIBE KEYSPACES;"
```

You should see your keyspace (e.g., `target_ks` or `migration`) in the list.

### Verify Data Replication
```bash
# Check data in source database (testdb)
mariadb -h localhost -u root -prootpassword testdb -e "SELECT COUNT(*) FROM animals;"

# Check data in ScyllaDB-backed database (scylla_db)
mariadb -h localhost -u root -prootpassword testdb -e "SELECT COUNT(*) FROM scylla_db.animals;"

# Check data in ScyllaDB directly
docker exec -it scylladb-migration-target cqlsh -e "SELECT COUNT(*) FROM target_ks.animals;"
```

All three counts should match.

## Common Issues

### Docker Not Found
Make sure Docker (or Colima on macOS) is running:
```bash
docker ps
```

If using Colima:
```bash
colima start --memory 8 --cpu 4
```

### MariaDB Build Fails
Ensure you have at least 8GB of memory allocated to Docker/Colima:
```bash
colima start --memory 8 --cpu 4
```

### Storage Engine Not Loaded
Verify the storage engine files are in the repository root:
```bash
ls -la *.cc *.h *.cmake CMakeLists.txt
```

### Connection Refused
Wait for containers to fully start (30-60 seconds for ScyllaDB):
```bash
docker logs scylladb-migration-target
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the Python scripts to understand the migration process
- Customize for your own database schema
- Review the [mariadb-scylla-storage-engine](https://github.com/GeoffMontee/mariadb-scylla-storage-engine) documentation

## Cleaning Up

To remove all containers and start fresh:
```bash
python3 destroy_db_containers.py
```

To also rebuild the MariaDB image:
```bash
python3 destroy_db_containers.py
python3 start_db_containers.py --rebuild
```

## Support

For issues and questions:
- Open an issue on GitHub
- Check the [mariadb-scylla-storage-engine](https://github.com/GeoffMontee/mariadb-scylla-storage-engine) repository
- Review the [postgres-to-scylla-migration](https://github.com/GeoffMontee/postgres-to-scylla-migration) repository for comparison
