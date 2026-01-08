# MariaDB to ScyllaDB Migration Tools

A collection of Python scripts and utilities to facilitate migration from MariaDB to ScyllaDB using the mariadb-scylla-storage-engine for real-time replication.

## Overview

This project provides automated tools to:
- Set up MariaDB and ScyllaDB Docker containers with proper networking
- Install and configure the MariaDB ScyllaDB storage engine
- Create matching ScyllaDB-backed tables in a separate database
- Set up triggers for real-time replication from source tables to ScyllaDB
- Migrate existing data safely without modifying source tables

## Built on mariadb-scylla-storage-engine

This migration toolkit is built on top of [mariadb-scylla-storage-engine](https://github.com/GeoffMontee/mariadb-scylla-storage-engine), a storage engine for MariaDB that enables seamless integration with ScyllaDB. The storage engine allows MariaDB to directly write to ScyllaDB tables, enabling real-time data replication.

For more information about the storage engine, including its features, limitations, and configuration options, visit the [mariadb-scylla-storage-engine GitHub repository](https://github.com/GeoffMontee/mariadb-scylla-storage-engine).

## Prerequisites

### Required Software
- **Docker** (or Colima on macOS)
- **Python 3.8+**
- **MariaDB client tools** (for mariadb command and health checks)
  ```bash
  brew install mariadb  # macOS
  ```

### Python Dependencies
```bash
pip install docker mariadb scylla-driver
```

### Docker Configuration (macOS with Colima)
If using Colima instead of Docker Desktop, set the Docker socket path:
```bash
# Add to ~/.bashrc or ~/.zshrc
export DOCKER_HOST='unix:///Users/YOUR_USERNAME/.colima/default/docker.sock'

# Increase Colima memory (recommended for building MariaDB from source)
colima stop
colima start --memory 8 --cpu 4
```

## Scripts

### 1. start_db_containers.py

Manages MariaDB and ScyllaDB Docker containers with automatic health checks.

**What it does:**
- Builds MariaDB from source with ScyllaDB storage engine (automatically clones storage engine repo)
- Downloads ScyllaDB 2025.4 Docker image
- Creates a shared Docker network for container communication
- Starts MariaDB on port 3306
- Starts ScyllaDB on ports 9042, 9142, 19042, 19142
- Verifies database health with connection tests

**Usage:**
```bash
# Basic usage
python3 start_db_containers.py

# Rebuild MariaDB image
python3 start_db_containers.py --rebuild
```

**Command-line Options:**
- `--rebuild` - Force rebuild of MariaDB Docker image

**Connection Information:**
- **MariaDB** (from host): `mariadb://root:rootpassword@localhost:3306/`
- **MariaDB** (from containers): `mariadb-migration-source:3306`
- **ScyllaDB** (from host): `localhost:9042`
- **ScyllaDB** (from containers): `scylladb-migration-target:9042`

### 2. setup_migration.py

Sets up the migration infrastructure between MariaDB and ScyllaDB using trigger-based replication.

**What it does:**
- Configures MariaDB ScyllaDB storage engine
- Creates a separate database (default: `scylla_db`) for ScyllaDB-backed tables
- Creates ScyllaDB keyspace
- For each table in the source database:
  - Creates a matching table in ScyllaDB
  - Creates a ScyllaDB-backed table in the `scylla_db` database
  - Creates INSERT/UPDATE/DELETE triggers on source tables to replicate to ScyllaDB
  - Migrates existing data using `INSERT INTO scylla_db.table SELECT * FROM source_db.table`

**Key Benefits:**
- **Safe**: Source tables remain unchanged, preserving original data and engine
- **Separate namespace**: ScyllaDB-backed tables live in a different database
- **Automatic replication**: Triggers propagate all changes in real-time
- **Rollback-friendly**: Can easily disable replication by dropping triggers

**Usage:**
```bash
# Basic usage (with defaults)
python3 setup_migration.py

# Custom database and keyspace
python3 setup_migration.py \
  --mariadb-database testdb \
  --mariadb-scylla-database scylla_db \
  --scylla-ks target_ks

# Full options
python3 setup_migration.py \
  --mariadb-host localhost \
  --mariadb-port 3306 \
  --mariadb-user root \
  --mariadb-password rootpassword \
  --mariadb-database testdb \
  --mariadb-docker-container mariadb-migration-source \
  --scylla-host localhost \
  --scylla-port 9042 \
  --scylla-ks migration \
  --scylla-fdw-host scylladb-migration-target \
  --scylla-docker-container scylladb-migration-target
```

**Command-line Options:**

MariaDB options:
- `--mariadb-host` - MariaDB host (default: localhost)
- `--mariadb-port` - MariaDB port (default: 3306)
- `--mariadb-user` - MariaDB user (default: root)
- `--mariadb-password` - MariaDB password (default: rootpassword)
- `--mariadb-database` - Source MariaDB database (default: testdb)
- `--mariadb-scylla-database` - Database for ScyllaDB-backed tables (default: scylla_db)
- `--mariadb-docker-container` - Container name (default: mariadb-migration-source)

ScyllaDB options:
- `--scylla-host` - ScyllaDB host for Python connection (default: localhost)
- `--scylla-port` - ScyllaDB CQL port (default: 9042)
- `--scylla-ks` - ScyllaDB keyspace name (default: migration)
- `--scylla-fdw-host` - ScyllaDB host for storage engine (default: scylladb-migration-target)
- `--scylla-docker-container` - Container name (default: scylladb-migration-target)

### 3. destroy_db_containers.py

Cleans up all Docker containers and resources created by the migration toolkit.

**What it does:**
- Stops and removes MariaDB container
- Stops and removes ScyllaDB container
- Removes the shared Docker network
- Cleans up associated volumes

**Usage:**
```bash
python3 destroy_db_containers.py
```

The script will prompt for confirmation before destroying any resources. This is useful for:
- Cleaning up after testing
- Starting fresh with new containers
- Freeing up system resources

**Warning:** This operation is destructive and will delete all data in the containers.

### 4. modify_sample_mariadb_data.py

Modifies sample MariaDB data to test replication to ScyllaDB.

**What it does:**
- Performs INSERT operations (3 animals, 2 habitats, 2 feedings with IDs 10001+)
- Performs UPDATE operations on newly inserted records
- Performs DELETE operations on selected records
- Provides verification commands to check replication

**Usage:**
```bash
# Basic usage (with defaults)
python3 modify_sample_mariadb_data.py

# Custom database and keyspace
python3 modify_sample_mariadb_data.py \
  --mariadb-database testdb \
  --scylla-ks target_ks
```

**Command-line Options:**
- `--mariadb-host` - MariaDB host (default: localhost)
- `--mariadb-port` - MariaDB port (default: 3306)
- `--mariadb-user` - MariaDB user (default: root)
- `--mariadb-password` - MariaDB password (default: rootpassword)
- `--mariadb-database` - MariaDB database (default: testdb)
- `--scylla-ks` - ScyllaDB keyspace name (default: migration)

## Quick Start Guide

### Step 1: Start Database Containers
```bash
python3 start_db_containers.py
```

Wait for both containers to be healthy and ready. The MariaDB build from source will take 15-30 minutes on first run.

### Step 2: Load Sample Schema and Data (Optional)
```bash
# Load schema
mariadb -h 127.0.0.1 -u root -prootpassword testdb < sample_mariadb_schema.sql

# Load data (1000 rows per table)
mariadb -h 127.0.0.1 -u root -prootpassword testdb < sample_mariadb_data.sql
```

### Step 3: Setup Migration Infrastructure
```bash
python3 setup_migration.py \
  --mariadb-database testdb \
  --mariadb-scylla-database scylla_db \
  --scylla-ks target_ks
```

### Step 4: Test Replication

**Option A: Use the test script (recommended)**
```bash
python3 modify_sample_mariadb_data.py \
  --mariadb-database testdb \
  --scylla-ks target_ks
```

This will perform INSERT, UPDATE, and DELETE operations on source tables and show you verification commands.

**Option B: Manual testing**
```bash
# Connect to MariaDB
mariadb -h 127.0.0.1 -u root -prootpassword testdb

# Insert data into source table (testdb)
INSERT INTO animals (animal_id, name, species, age, weight_kg, habitat_name, last_checkup)
VALUES (9999, 'Test Tiger', 'Tiger', 5, 200.5, 'Forest', '2024-01-01');

# Query source table
SELECT * FROM testdb.animals WHERE animal_id = 9999;

# Query ScyllaDB-backed table in MariaDB
SELECT * FROM scylla_db.animals WHERE animal_id = 9999;

# Connect to ScyllaDB to verify
docker exec -it scylladb-migration-target cqlsh
USE target_ks;
SELECT * FROM animals WHERE animal_id = 9999;
```

## Sample Data

The project includes sample animal-themed schema and data:

### sample_mariadb_schema.sql
Creates 4 tables:
- `animals` - Animal records with species, age, weight
- `habitats` - Habitat information with climate and capacity
- `feedings` - Feeding logs with food types and quantities
- `equipment` - Equipment records testing additional data types (BIGINT, SMALLINT, TEXT, FLOAT, DOUBLE, BOOLEAN, UUID, TIME)

### sample_mariadb_data.sql
Generates 1000 rows per table using MariaDB's sequences.

## Architecture

```
┌─────────────────────────────────────┐         ┌──────────────────────┐
│  MariaDB                            │         │  ScyllaDB            │
│  (Source)                           │         │  (Target)            │
├─────────────────────────────────────┤         ├──────────────────────┤
│                                     │         │                      │
│  testdb (source database)           │         │  target_ks keyspace  │
│  ├─ animals (InnoDB)                │         │  ├─ animals          │
│  ├─ habitats (InnoDB)               │         │  ├─ habitats         │
│  └─ feedings (InnoDB)               │         │  └─ feedings         │
│       │                             │         │       ▲              │
│       │ triggers                    │         │       │              │
│       ▼                             │         │       │              │
│  scylla_db (replication database)   │─────────────────┘              │
│  ├─ animals (ENGINE=SCYLLA) ────────┼─────────────────────────────────>
│  ├─ habitats (ENGINE=SCYLLA) ───────┼─────────────────────────────────>
│  └─ feedings (ENGINE=SCYLLA) ───────┼─────────────────────────────────>
│                                     │         │                      │
└─────────────────────────────────────┘         └──────────────────────┘
         │                                               │
         └───────────────────┬───────────────────────────┘
                        migration-network
                        (Docker bridge)
```

**Data Flow:**
1. Application writes to `testdb.animals` (InnoDB table)
2. INSERT/UPDATE/DELETE triggers fire automatically
3. Triggers replicate changes to `scylla_db.animals` (ENGINE=SCYLLA)
4. ScyllaDB storage engine writes to ScyllaDB cluster

## How It Works

1. **Storage Engine Configuration**: The MariaDB ScyllaDB storage engine is configured to connect to the ScyllaDB cluster.

2. **Separate Database**: A separate database (`scylla_db`) is created to hold ScyllaDB-backed tables, keeping source tables unchanged.

3. **Table Replication**: For each source table, a matching table with `ENGINE=SCYLLA` is created in the `scylla_db` database.

4. **Trigger-Based Replication**: Three triggers (INSERT, UPDATE, DELETE) are created on each source table to automatically propagate changes to the corresponding ScyllaDB-backed table.

5. **Existing Data Migration**: Existing data is copied using `INSERT INTO scylla_db.table SELECT * FROM source_db.table`.

6. **Ongoing Replication**: All future changes to source tables are automatically replicated to ScyllaDB via triggers.

## Requirements and Limitations

### Type Mapping

| MariaDB Type | ScyllaDB Type | Notes |
|--------------|---------------|-------|
| `TINYINT` | `tinyint` | |
| `SMALLINT` | `smallint` | |
| `INT` | `int` | |
| `BIGINT` | `bigint` | |
| `FLOAT` | `float` | |
| `DOUBLE` | `double` | |
| `DECIMAL` | `decimal` | |
| `VARCHAR`, `TEXT` | `text` | |
| `VARBINARY`, `BLOB` | `blob` | |
| `DATE` | `date` | |
| `TIME` | `time` | |
| `DATETIME`, `TIMESTAMP` | `timestamp` | |
| `UUID` | `uuid` | Via MariaDB UUID functions |

### Limitations

1. **Primary Keys**: Required for all tables
2. **Transactions**: Limited transaction support
3. **Foreign Keys**: Not supported
4. **Joins**: No join support (denormalize your data)
5. **Secondary Indexes**: Limited support
6. **Auto Increment**: Not recommended (use UUIDs instead)

## Maintenance Commands

### Clean Up Everything (Recommended)
```bash
python3 destroy_db_containers.py
```
This removes all containers, networks, and volumes with confirmation prompts.

### Stop Containers
```bash
docker stop mariadb-migration-source scylladb-migration-target
```

### Start Stopped Containers
```bash
docker start mariadb-migration-source scylladb-migration-target
```

### Remove Containers (Manual)
```bash
docker rm -f mariadb-migration-source scylladb-migration-target
```

### Remove Network (Manual)
```bash
docker network rm migration-network
```

### View Logs
```bash
# MariaDB logs
docker logs mariadb-migration-source

# ScyllaDB logs
docker logs scylladb-migration-target
```

### Rerun Migration Setup
The setup script is idempotent and can be run multiple times:
```bash
# Will update existing configuration
python3 setup_migration.py
```

## Troubleshooting

### MariaDB Won't Connect
```bash
# Check if container is running
docker ps | grep mariadb

# Check MariaDB logs
docker logs mariadb-migration-source

# Test connection
mariadb -h 127.0.0.1 -u root -prootpassword -e "SELECT 1;"
```

### ScyllaDB Memory Issues
```bash
# Increase Colima memory
colima stop
colima start --memory 4 --cpu 2

# Or adjust ScyllaDB memory in start_db_containers.py
# Change: --memory 400M to --memory 750M
```

### Storage Engine Build Errors
```bash
# Check if build dependencies are available
docker exec mariadb-migration-source dpkg -l | grep build-essential

# Rebuild manually
python3 start_db_containers.py --rebuild
```

### Verify Replication
```bash
# Count rows in MariaDB
mariadb -h 127.0.0.1 -u root -prootpassword testdb -e "SELECT COUNT(*) FROM animals;"

# Directly in ScyllaDB
docker exec -it scylladb-migration-target cqlsh -e "SELECT COUNT(*) FROM target_ks.animals;"
```

## Contributing

Feel free to open issues or submit pull requests for improvements.

## License

MIT License - See LICENSE file for details
