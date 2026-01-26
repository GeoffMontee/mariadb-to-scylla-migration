# GitHub Copilot Instructions

## Project Overview

This is a MariaDB to ScyllaDB migration toolkit that uses **trigger-based replication** to safely replicate data from MariaDB to ScyllaDB. The toolkit is based on the [postgres-to-scylla-migration](https://github.com/scylladb/postgres-to-scylla-migration) project but adapted for MariaDB.

### Key Technologies
- **MariaDB 12.1.2** - Built from source with ScyllaDB storage engine
- **ScyllaDB 2025.4** - NoSQL database (Cassandra-compatible)
- **mariadb-scylla-storage-engine** - Storage engine plugin for MariaDB
- **Python 3.8+** - Automation scripts
- **MariaDB Connector/Python** (`mariadb` module) - Python database driver
- **scylla-driver** (`cassandra-driver` fork) - Python CQL driver
- **Docker/Colima** - Container runtime for databases

## Architecture Pattern: Trigger-Based Replication

### CRITICAL: Two-Database Design

This toolkit uses a **safe, non-destructive approach** with two separate databases:

1. **Source Database** (default: `testdb`)
   - Contains original tables with native storage engines (InnoDB, MyISAM, etc.)
   - **NEVER modified** by migration toolkit
   - Applications read/write here normally

2. **ScyllaDB-Backed Database** (default: `scylla_db`)
   - Contains tables with `ENGINE=SCYLLA`
   - Mirrors source tables
   - Writes go directly to ScyllaDB cluster

### Replication Flow
```
Application → testdb.table (InnoDB)
                    ↓ triggers
              scylla_db.table (ENGINE=SCYLLA)
                    ↓
              ScyllaDB cluster
```

## Code Conventions

### Database Connections

**ALWAYS use `mariadb` module for MariaDB connections:**
```python
import mariadb

conn = mariadb.connect(
    host='localhost',
    port=3306,
    user='root',
    password='rootpassword',
    database='testdb'
)
```

**ALWAYS use `cassandra.cluster` for ScyllaDB connections:**
```python
from cassandra.cluster import Cluster

cluster = Cluster(['localhost'], port=9042)
session = cluster.connect()
```

### SQL Patterns

**Use backticks for identifiers to avoid reserved word conflicts:**
```python
f"SELECT * FROM `{database}`.`{table}`"
```

**Always specify database when accessing tables across databases:**
```python
# Good
cursor.execute("SELECT * FROM testdb.animals WHERE animal_id = 1")
cursor.execute("SELECT * FROM scylla_db.animals WHERE animal_id = 1")

# Bad - ambiguous
cursor.execute("SELECT * FROM animals WHERE animal_id = 1")
```

### Trigger Creation Pattern

For each source table, create three triggers:

```python
# INSERT trigger
f"""
CREATE TRIGGER `{source_db}`.`{table}_insert_trigger`
AFTER INSERT ON `{source_db}`.`{table}`
FOR EACH ROW
BEGIN
    INSERT INTO `{scylla_db}`.`{table}` ({col_list})
    VALUES ({new_col_list});
END
"""

# UPDATE trigger (delete + insert pattern for ScyllaDB)
f"""
CREATE TRIGGER `{source_db}`.`{table}_update_trigger`
AFTER UPDATE ON `{source_db}`.`{table}`
FOR EACH ROW
BEGIN
    DELETE FROM `{scylla_db}`.`{table}` WHERE {pk_where_clause};
    INSERT INTO `{scylla_db}`.`{table}` ({col_list})
    VALUES ({new_col_list});
END
"""

# DELETE trigger
f"""
CREATE TRIGGER `{source_db}`.`{table}_delete_trigger`
AFTER DELETE ON `{source_db}`.`{table}`
FOR EACH ROW
BEGIN
    DELETE FROM `{scylla_db}`.`{table}` WHERE {pk_where_clause};
END
"""
```

### Debug Logging

When `--mariadb-verbose` is enabled:

1. **Debug table is created** in the source database:
```python
f"""
CREATE TABLE IF NOT EXISTS `{database}`.`_trigger_debug_log` (
    log_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    log_timestamp TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
    table_name VARCHAR(64) NOT NULL,
    trigger_name VARCHAR(64) NOT NULL,
    event_type ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    phase ENUM('START', 'END') NOT NULL,
    primary_key_value VARCHAR(255),
    INDEX idx_timestamp (log_timestamp),
    INDEX idx_table (table_name, log_timestamp)
) ENGINE=InnoDB
"""
```

2. **Triggers log both to SIGNAL and debug table**:
```python
# Insert trigger with debug logging
f"""
CREATE TRIGGER `{source_db}`.`{table}_insert_trigger`
AFTER INSERT ON `{source_db}`.`{table}`
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '01000' SET MESSAGE_TEXT = 'DEBUG: {table}_insert_trigger START';
    INSERT INTO `{source_db}`.`_trigger_debug_log` (table_name, trigger_name, event_type, phase, primary_key_value)
    VALUES ('{table}', '{table}_insert_trigger', 'INSERT', 'START', CAST(NEW.`{pk_col}` AS CHAR));
    
    INSERT INTO `{scylla_db}`.`{table}` ({col_list})
    VALUES ({new_col_list});
    
    INSERT INTO `{source_db}`.`_trigger_debug_log` (table_name, trigger_name, event_type, phase, primary_key_value)
    VALUES ('{table}', '{table}_insert_trigger', 'INSERT', 'END', CAST(NEW.`{pk_col}` AS CHAR));
    SIGNAL SQLSTATE '01000' SET MESSAGE_TEXT = 'DEBUG: {table}_insert_trigger END';
END
"""
```

3. **Query debug logs**:
```sql
-- Recent trigger executions
SELECT * FROM testdb._trigger_debug_log 
ORDER BY log_timestamp DESC LIMIT 100;

-- Check for incomplete executions (START without END)
SELECT d1.*
FROM testdb._trigger_debug_log d1
LEFT JOIN testdb._trigger_debug_log d2
  ON d1.trigger_name = d2.trigger_name
  AND d1.primary_key_value = d2.primary_key_value
  AND d1.phase = 'START' AND d2.phase = 'END'
  AND d2.log_timestamp > d1.log_timestamp
WHERE d1.phase = 'START' AND d2.log_id IS NULL;
```

**Important notes:**
- `_trigger_debug_log` is automatically excluded from migration (tables starting with `_`)
- Uses MariaDB-only features: AUTO_INCREMENT, ENUM, microsecond timestamps
- Provides both SIGNAL warnings (immediate feedback) and table logging (reliable history)
- Log to both locations to maximize debugging visibility

### ScyllaDB-Backed Table Creation

```python
f"""
CREATE TABLE IF NOT EXISTS `{scylla_db}`.`{table}` (
    {column_definitions}
) ENGINE=SCYLLA
CONNECTION='keyspace={scylla_keyspace} table={table}'
"""
```

### Data Migration Pattern

```python
# Copy existing data using INSERT...SELECT
f"""
INSERT INTO `{scylla_db}`.`{table}`
SELECT * FROM `{source_db}`.`{table}`
"""
```

## Important Constraints

### Internal Tables
- **Tables starting with underscore are excluded** from migration
- Used for internal/system tables like `_trigger_debug_log`
- Filter pattern: `AND table_name NOT LIKE '\\_%'` in `get_source_tables()`

### Primary Keys Required
- **All tables MUST have a primary key** for ScyllaDB
- ScyllaDB uses primary key as partition key
- No auto-detection of partition keys - first PK column is used

### Type Mappings (MariaDB → CQL)
```python
{
    'tinyint': 'tinyint',
    'smallint': 'smallint',
    'int': 'int',
    'bigint': 'bigint',
    'float': 'float',
    'double': 'double',
    'decimal': 'decimal',
    'varchar': 'text',
    'char': 'text',
    'text': 'text',
    'date': 'date',
    'time': 'time',
    'datetime': 'timestamp',
    'timestamp': 'timestamp',
    'binary(16)': 'uuid',  # For UUID storage
    'char(36)': 'uuid',    # For UUID storage
    'blob': 'blob',
}
```

### Storage Engine Configuration

Global variables must be set before using ENGINE=SCYLLA:
```sql
SET GLOBAL scylla_hosts = 'scylladb-migration-target';
SET GLOBAL scylla_port = 9042;
SET GLOBAL scylla_keyspace = 'target_ks';
```

## Docker Container Names

**Standard container names (do not change without good reason):**
- MariaDB: `mariadb-migration-source`
- ScyllaDB: `scylladb-migration-target`
- Network: `migration-network`

## File Structure

```
.
├── start_db_containers.py      # Build & start Docker containers
├── setup_migration.py          # Setup triggers and tables
├── modify_sample_mariadb_data.py  # Test script
├── destroy_db_containers.py    # Cleanup script
├── Dockerfile                  # MariaDB build with storage engine
├── docker-entrypoint.sh        # MariaDB initialization
├── sample_mariadb_schema.sql   # Test schema (4 tables)
├── sample_mariadb_data.sql     # Test data (1000 rows/table)
├── requirements.txt            # Python dependencies
├── reset.sh                    # Full reset script
└── TRIGGER_BASED_REPLICATION.md  # Architecture documentation
```

## Common Tasks

### Adding a New Python Script

Always:
1. Use `#!/usr/bin/env python3` shebang
2. Include argparse for command-line arguments
3. Use `mariadb` module (not PyMySQL, mysql-connector, etc.)
4. Handle exceptions gracefully with try/except
5. Make executable: `chmod +x script.py`

### Querying Data for Verification

```python
# Check source
cursor.execute(f"SELECT COUNT(*) FROM `{source_db}`.`{table}`")
source_count = cursor.fetchone()[0]

# Check ScyllaDB via MariaDB
cursor.execute(f"SELECT COUNT(*) FROM `{scylla_db}`.`{table}`")
scylla_count = cursor.fetchone()[0]

# Compare
if source_count != scylla_count:
    print(f"⚠ Mismatch: source={source_count}, scylla={scylla_count}")
```

### Checking Trigger Status

```python
cursor.execute(f"""
    SELECT trigger_name, event_manipulation, action_statement
    FROM information_schema.triggers
    WHERE trigger_schema = '{source_db}'
    AND event_object_table = '{table}'
    ORDER BY trigger_name
""")
```

### Debugging Trigger Execution

```python
# Check recent trigger activity (requires --mariadb-verbose mode)
cursor.execute(f"""
    SELECT 
        table_name,
        trigger_name,
        event_type,
        COUNT(*) as executions,
        MAX(log_timestamp) as last_execution
    FROM `{source_db}`.`_trigger_debug_log`
    GROUP BY table_name, trigger_name, event_type
    ORDER BY last_execution DESC
""")

# Find incomplete trigger executions (START without END)
cursor.execute(f"""
    SELECT d1.*
    FROM `{source_db}`.`_trigger_debug_log` d1
    LEFT JOIN `{source_db}`.`_trigger_debug_log` d2
      ON d1.trigger_name = d2.trigger_name
      AND d1.primary_key_value = d2.primary_key_value
      AND d1.phase = 'START'
      AND d2.phase = 'END'
      AND d2.log_timestamp > d1.log_timestamp
    WHERE d1.phase = 'START' AND d2.log_id IS NULL
    ORDER BY d1.log_timestamp DESC
    LIMIT 20
""")
```

## Error Patterns and Solutions

### "Storage engine SCYLLA is disabled"
```python
# Solution: Install plugin
cursor.execute("INSTALL SONAME 'ha_scylla'")
```

### "Table must have a primary key"
```python
# Always check before processing
cursor.execute(f"""
    SELECT COUNT(*)
    FROM information_schema.key_column_usage
    WHERE table_schema = '{database}'
    AND table_name = '{table}'
    AND constraint_name = 'PRIMARY'
""")
if cursor.fetchone()[0] == 0:
    print(f"✗ Table '{table}' has no primary key, skipping")
    return
```

### Trigger fails on UPDATE
```python
# Use DELETE + INSERT pattern instead of UPDATE
# ScyllaDB doesn't support UPDATE directly via storage engine
DELETE FROM scylla_db.table WHERE id = OLD.id;
INSERT INTO scylla_db.table VALUES (NEW.id, NEW.name, ...);
```

## Testing Best Practices

### Test Replication Chain
```python
# 1. Insert into source
cursor.execute(f"INSERT INTO {source_db}.test_table VALUES (...)")

# 2. Verify in scylla_db via MariaDB
cursor.execute(f"SELECT * FROM {scylla_db}.test_table WHERE id = ...")

# 3. Verify in ScyllaDB directly
session.execute(f"SELECT * FROM {keyspace}.test_table WHERE id = ...")
```

### Performance Testing
```python
import time

# Measure trigger overhead
start = time.time()
cursor.execute(f"INSERT INTO {source_db}.table VALUES (...)")
elapsed = time.time() - start
print(f"Insert with trigger: {elapsed:.3f}s")
```

## Security Notes

- Default credentials are for **development only**: `root:rootpassword`
- Never commit real credentials to git
- Use environment variables for production:
  ```python
  import os
  password = os.getenv('MARIADB_PASSWORD', 'rootpassword')
  ```

## Build Context

### MariaDB Source Build
- Takes 15-30 minutes on first run
- Requires 8GB+ memory (use `colima start --memory 8`)
- Compiles MariaDB 12.1.2 with ScyllaDB storage engine
- Includes Rust toolchain for cpp-rs-driver

### Storage Engine Dependencies
The Dockerfile automatically clones the storage engine repository and copies these files during the Docker build:
- `ha_scylla.cc` / `ha_scylla.h`
- `scylla_connection.cc` / `scylla_connection.h`
- `scylla_types.cc` / `scylla_types.h`
- `scylla_query.cc` / `scylla_query.h`
- `plugin.cmake`
- `CMakeLists.txt`

No manual file copying is required.

## Helpful Commands

### Connect to MariaDB
```bash
mariadb -h localhost -u root -prootpassword testdb
```

### Connect to ScyllaDB
```bash
docker exec -it scylladb-migration-target cqlsh
```

### Check Container Logs
```bash
docker logs mariadb-migration-source
docker logs scylladb-migration-target
```

### View Triggers
```sql
SHOW TRIGGERS FROM testdb;
SHOW CREATE TRIGGER testdb.animals_insert_trigger;
```

### Check Replication Status
```sql
SELECT 
    t1.cnt as source_count,
    t2.cnt as scylla_count,
    t1.cnt - t2.cnt as difference
FROM 
    (SELECT COUNT(*) as cnt FROM testdb.animals) t1,
    (SELECT COUNT(*) as cnt FROM scylla_db.animals) t2;
```

## When Making Changes

### Never Modify Source Tables
- Do NOT run `ALTER TABLE testdb.table ENGINE=SCYLLA`
- Do NOT run `DROP TABLE testdb.table`
- Only create triggers on source tables
- Only create ENGINE=SCYLLA tables in scylla_db

### Always Clean Up Triggers
When removing a table from replication:
```python
for trigger_type in ['insert', 'update', 'delete']:
    cursor.execute(f"DROP TRIGGER IF EXISTS `{source_db}`.`{table}_{trigger_type}_trigger`")
```

### Test in Isolation
Before modifying replication logic:
1. Create test table in testdb
2. Create test table in scylla_db
3. Create triggers
4. Test INSERT/UPDATE/DELETE
5. Verify in both databases
6. Clean up test tables and triggers

## References

- [mariadb-scylla-storage-engine](https://github.com/GeoffMontee/mariadb-scylla-storage-engine)
- [postgres-to-scylla-migration](https://github.com/scylladb/postgres-to-scylla-migration)
- [ScyllaDB Documentation](https://docs.scylladb.com/)
- [MariaDB Documentation](https://mariadb.com/kb/en/)
