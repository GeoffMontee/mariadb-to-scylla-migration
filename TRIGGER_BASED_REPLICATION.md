# Trigger-Based Replication Approach

## Overview

This toolkit uses a **trigger-based replication** approach to safely migrate data from MariaDB to ScyllaDB. This is a safer alternative to converting existing tables in-place, as it preserves the original tables and storage engines.

## Architecture

### Two-Database Design

The toolkit creates and uses two separate databases:

1. **Source Database** (default: `testdb`)
   - Contains your original tables with their native storage engines (e.g., InnoDB)
   - These tables are **never modified** by the migration toolkit
   - Applications continue to read/write to these tables normally

2. **ScyllaDB-Backed Database** (default: `scylla_db`)
   - Contains tables with `ENGINE=SCYLLA`
   - Each table mirrors a corresponding source table
   - Writes to these tables are sent directly to ScyllaDB

### Replication Flow

```
Application writes to testdb.animals (InnoDB)
            ↓
    Trigger fires automatically
            ↓
    Replicates to scylla_db.animals (ENGINE=SCYLLA)
            ↓
    ScyllaDB storage engine writes to ScyllaDB cluster
```

## Implementation Details

### Step 1: Create ScyllaDB Database

```sql
CREATE DATABASE IF NOT EXISTS scylla_db;
```

### Step 2: Create ScyllaDB-Backed Table

For each source table, create a matching table in `scylla_db`:

```sql
CREATE TABLE scylla_db.animals (
    animal_id INT NOT NULL,
    name VARCHAR(100),
    species VARCHAR(100),
    -- ... other columns ...
    PRIMARY KEY (animal_id)
) ENGINE=SCYLLA CONNECTION='keyspace=target_ks table=animals';
```

### Step 3: Create Replication Triggers

Three triggers are created for each table:

#### INSERT Trigger
```sql
CREATE TRIGGER testdb.animals_insert_trigger
AFTER INSERT ON testdb.animals
FOR EACH ROW
BEGIN
    INSERT INTO scylla_db.animals (animal_id, name, species, ...)
    VALUES (NEW.animal_id, NEW.name, NEW.species, ...);
END;
```

#### UPDATE Trigger
```sql
CREATE TRIGGER testdb.animals_update_trigger
AFTER UPDATE ON testdb.animals
FOR EACH ROW
BEGIN
    DELETE FROM scylla_db.animals WHERE animal_id = OLD.animal_id;
    INSERT INTO scylla_db.animals (animal_id, name, species, ...)
    VALUES (NEW.animal_id, NEW.name, NEW.species, ...);
END;
```

#### DELETE Trigger
```sql
CREATE TRIGGER testdb.animals_delete_trigger
AFTER DELETE ON testdb.animals
FOR EACH ROW
BEGIN
    DELETE FROM scylla_db.animals WHERE animal_id = OLD.animal_id;
END;
```

### Step 4: Migrate Existing Data

```sql
INSERT INTO scylla_db.animals
SELECT * FROM testdb.animals;
```

## Benefits

1. **Safety**: Source tables remain completely unchanged
2. **Rollback**: Can easily disable replication by dropping triggers
3. **Testing**: Can query both databases to verify consistency
4. **Flexibility**: Can modify ScyllaDB schema independently
5. **Transparency**: Clear separation between source and target data

## Verification

### Query Source Data
```sql
SELECT * FROM testdb.animals WHERE animal_id = 123;
```

### Query ScyllaDB via MariaDB
```sql
SELECT * FROM scylla_db.animals WHERE animal_id = 123;
```

### Query ScyllaDB Directly
```bash
docker exec -it scylladb-migration-target cqlsh
USE target_ks;
SELECT * FROM animals WHERE animal_id = 123;
```

All three queries should return identical results.

## Disabling Replication

To stop replication without affecting source data:

```sql
DROP TRIGGER IF EXISTS testdb.animals_insert_trigger;
DROP TRIGGER IF EXISTS testdb.animals_update_trigger;
DROP TRIGGER IF EXISTS testdb.animals_delete_trigger;
```

## Re-enabling Replication

Simply run `setup_migration.py` again to recreate triggers and resync data.

## Performance Considerations

- **Write Performance**: Each write to a source table triggers additional writes to ScyllaDB
- **Synchronous**: Triggers execute synchronously, so write latency increases
- **Network**: Trigger execution requires network round-trip to ScyllaDB
- **Recommendation**: Monitor write performance and consider async replication for high-throughput scenarios

## Comparison with In-Place Conversion

| Aspect | Trigger-Based (This Toolkit) | In-Place Conversion |
|--------|------------------------------|---------------------|
| Source table modified | No | Yes (DROP and recreate) |
| Rollback | Easy (drop triggers) | Difficult (requires backup) |
| Risk level | Low | High |
| Testing | Can test both databases | Must test in production |
| Storage engines | Source keeps original | All become ENGINE=SCYLLA |
| Write performance | ~2x overhead (trigger) | Direct to ScyllaDB |

## Monitoring Replication

### Check Trigger Status
```sql
SHOW TRIGGERS FROM testdb WHERE `Trigger` LIKE '%_trigger';
```

### Verify Row Counts
```sql
SELECT 
    'source' as database, COUNT(*) as row_count 
FROM testdb.animals
UNION ALL
SELECT 
    'scylla_db' as database, COUNT(*) as row_count 
FROM scylla_db.animals;
```

## Troubleshooting

### Triggers Not Firing

Check trigger syntax:
```sql
SHOW CREATE TRIGGER testdb.animals_insert_trigger;
```

### Data Mismatch

Compare row counts:
```bash
python3 -c "
import mariadb
conn = mariadb.connect(host='localhost', user='root', password='rootpassword', database='testdb')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM testdb.animals')
source_count = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM scylla_db.animals')
scylla_count = cur.fetchone()[0]
print(f'Source: {source_count}, ScyllaDB: {scylla_count}')
"
```

### Trigger Errors

Check MariaDB error log:
```bash
docker exec mariadb-migration-source cat /var/log/mysql/error.log | grep -i trigger
```
