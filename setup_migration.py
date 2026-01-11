#!/usr/bin/env python3
"""
Setup migration infrastructure between MariaDB and ScyllaDB.
Configures the ScyllaDB storage engine and creates tables.
"""

import argparse
import sys
import mariadb
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider


def main():
    """Main function to setup migration infrastructure."""
    args = parse_arguments()
    
    print("=" * 70)
    print("MariaDB to ScyllaDB Migration Setup")
    print("=" * 70)
    
    # Step 1: Connect to databases
    print("\n[1/4] Connecting to databases...")
    mariadb_conn = connect_to_mariadb(args)
    scylla_session = connect_to_scylla(args)
    
    # Step 2: Configure MariaDB storage engine
    print("\n[2/5] Configuring MariaDB ScyllaDB storage engine...")
    configure_storage_engine(mariadb_conn, args)
    
    # Step 3: Create ScyllaDB database
    print("\n[3/5] Creating ScyllaDB database in MariaDB...")
    create_scylla_database(mariadb_conn, args.mariadb_scylla_database)
    
    # Step 4: Get tables and setup migration
    print("\n[4/5] Setting up table migration...")
    tables = get_source_tables(mariadb_conn, args.mariadb_database)
    
    if not tables:
        print(f"⚠ No tables found in database '{args.mariadb_database}'")
        sys.exit(0)
    
    print(f"Found {len(tables)} table(s) to migrate:")
    for table in tables:
        print(f"  - {table}")
    
    for table in tables:
        print(f"\nProcessing table: {table}")
        setup_table_migration(mariadb_conn, scylla_session, table, args)
    
    # Step 5: Migrate existing data
    print("\n[5/5] Migrating existing data...")
    for table in tables:
        migrate_table_data(mariadb_conn, args.mariadb_database, args.mariadb_scylla_database, table)
    
    # Cleanup
    mariadb_conn.close()
    scylla_session.shutdown()
    
    print("\n" + "=" * 70)
    print("✓ Migration setup completed successfully!")
    print("=" * 70)
    print("\nNext steps:")
    print(f"  1. Insert/Update/Delete data in '{args.mariadb_database}' tables")
    print(f"  2. Triggers will automatically replicate to '{args.mariadb_scylla_database}' (ScyllaDB)")
    print(f"  3. Query source: SELECT * FROM {args.mariadb_database}.<table_name>;")
    print(f"  4. Query ScyllaDB: SELECT * FROM {args.mariadb_scylla_database}.<table_name>;")
    print(f"  5. Verify in ScyllaDB: docker exec -it scylladb-migration-target cqlsh -e \"SELECT * FROM {args.scylla_ks}.<table_name>;\"")


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Setup MariaDB to ScyllaDB migration infrastructure",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # MariaDB options
    mariadb_group = parser.add_argument_group('MariaDB options')
    mariadb_group.add_argument('--mariadb-host', default='127.0.0.1',
                              help='MariaDB host')
    mariadb_group.add_argument('--mariadb-port', type=int, default=3306,
                              help='MariaDB port')
    mariadb_group.add_argument('--mariadb-user', default='root',
                              help='MariaDB user')
    mariadb_group.add_argument('--mariadb-password', default='rootpassword',
                              help='MariaDB password')
    mariadb_group.add_argument('--mariadb-database', default='testdb',
                              help='MariaDB source database')
    mariadb_group.add_argument('--mariadb-scylla-database', default='scylla_db',
                              help='MariaDB database for ScyllaDB-backed tables')
    mariadb_group.add_argument('--mariadb-docker-container', default='mariadb-migration-source',
                              help='MariaDB docker container name')
    mariadb_group.add_argument('--mariadb-verbose', action='store_true',
                              help='Enable verbose logging in ScyllaDB storage engine')
    
    # ScyllaDB options
    scylla_group = parser.add_argument_group('ScyllaDB options')
    scylla_group.add_argument('--scylla-host', default='localhost',
                              help='ScyllaDB host (use "scylladb-migration-target" for storage engine connection)')
    scylla_group.add_argument('--scylla-port', type=int, default=9042,
                              help='ScyllaDB CQL port')
    scylla_group.add_argument('--scylla-user', default=None,
                              help='ScyllaDB user (optional)')
    scylla_group.add_argument('--scylla-password', default=None,
                              help='ScyllaDB password (optional)')
    scylla_group.add_argument('--scylla-ks', default='migration',
                              help='ScyllaDB keyspace')
    scylla_group.add_argument('--scylla-fdw-host', default='scylladb-migration-target',
                              help='ScyllaDB host for storage engine connection (container name)')
    scylla_group.add_argument('--scylla-docker-container', default='scylladb-migration-target',
                              help='ScyllaDB docker container name')
    
    return parser.parse_args()


def connect_to_mariadb(args):
    """Connect to MariaDB database."""
    try:
        conn = mariadb.connect(
            host=args.mariadb_host,
            port=args.mariadb_port,
            user=args.mariadb_user,
            password=args.mariadb_password,
            database=args.mariadb_database
        )
        print(f"  ✓ Connected to MariaDB at {args.mariadb_host}:{args.mariadb_port}")
        return conn
    except Exception as e:
        print(f"✗ Failed to connect to MariaDB: {e}")
        sys.exit(1)


def connect_to_scylla(args):
    """Connect to ScyllaDB cluster."""
    try:
        if args.scylla_user and args.scylla_password:
            auth_provider = PlainTextAuthProvider(
                username=args.scylla_user,
                password=args.scylla_password
            )
            cluster = Cluster([args.scylla_host], port=args.scylla_port, auth_provider=auth_provider)
        else:
            cluster = Cluster([args.scylla_host], port=args.scylla_port)
        
        session = cluster.connect()
        print(f"  ✓ Connected to ScyllaDB at {args.scylla_host}:{args.scylla_port}")
        return session
    except Exception as e:
        print(f"✗ Failed to connect to ScyllaDB: {e}")
        sys.exit(1)


def configure_storage_engine(conn, args):
    """Configure MariaDB ScyllaDB storage engine (deprecated - using per-table COMMENT instead)."""
    # Global variables don't persist across restarts and aren't available in trigger context
    # Connection info is now embedded in each table's COMMENT field
    print(f"  ℹ Using per-table connection configuration (embedded in COMMENT)")


def create_scylla_database(conn, scylla_database):
    """Create database for ScyllaDB-backed tables."""
    cursor = conn.cursor()
    try:
        print(f"  Creating database '{scylla_database}'...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {scylla_database}")
        print(f"  ✓ Database '{scylla_database}' ready")
    except Exception as e:
        print(f"  ✗ Error creating database: {e}")
        raise
    finally:
        cursor.close()


def get_source_tables(conn, database):
    """Get list of tables in the source database."""
    cursor = conn.cursor()
    try:
        cursor.execute(f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = '{database}'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        return tables
    finally:
        cursor.close()


def get_table_schema(conn, database, table):
    """Get column definitions for a table."""
    cursor = conn.cursor()
    try:
        cursor.execute(f"""
            SELECT column_name, column_type, is_nullable, column_key
            FROM information_schema.columns
            WHERE table_schema = '{database}'
            AND table_name = '{table}'
            ORDER BY ordinal_position
        """)
        
        columns = []
        for row in cursor.fetchall():
            col_name, col_type, nullable, key = row
            columns.append({
                'name': col_name,
                'type': col_type,
                'nullable': nullable == 'YES',
                'is_primary': key == 'PRI'
            })
        
        return columns
    finally:
        cursor.close()


def create_mariadb_scylla_table(conn, source_database, scylla_database, scylla_keyspace, scylla_host, scylla_port, table, args):
    """Create a ScyllaDB-backed table in the scylla_database."""
    cursor = conn.cursor()
    try:
        # Get the schema from the source table
        columns = get_table_schema(conn, source_database, table)
        
        if not columns:
            print(f"  ✗ No columns found for {source_database}.{table}")
            return False
        
        # Build the CREATE TABLE statement
        column_defs = []
        primary_keys = []
        
        for col in columns:
            col_def = f"`{col['name']}` {col['type']}"
            if not col['nullable']:
                col_def += " NOT NULL"
            column_defs.append(col_def)
            
            if col['is_primary']:
                primary_keys.append(f"`{col['name']}`")
        
        # Add primary key constraint
        if primary_keys:
            column_defs.append(f"PRIMARY KEY ({', '.join(primary_keys)})")
        
        # Embed connection info in COMMENT (persists across restarts)
        comment = f"scylla_hosts={scylla_host};scylla_keyspace={scylla_keyspace};scylla_table={table}"
        
        # Add verbose option if enabled
        if args.mariadb_verbose:
            comment += ";scylla_verbose=true"
        
        create_stmt = f"""
            CREATE TABLE IF NOT EXISTS `{scylla_database}`.`{table}` (
                {', '.join(column_defs)}
            ) ENGINE=SCYLLA
            COMMENT='{comment}'
        """
        
        print(f"  Creating ScyllaDB-backed table {scylla_database}.{table}...")
        cursor.execute(create_stmt)
        print(f"  ✓ Table {scylla_database}.{table} created")
        return True
        
    except Exception as e:
        print(f"  ✗ Error creating table {scylla_database}.{table}: {e}")
        return False
    finally:
        cursor.close()


def create_replication_triggers(conn, source_database, scylla_database, table, args):
    """Create INSERT/UPDATE/DELETE triggers to replicate changes to ScyllaDB."""
    cursor = conn.cursor()
    try:
        # Get column names
        columns = get_table_schema(conn, source_database, table)
        if not columns:
            print(f"  ✗ No columns found for {source_database}.{table}")
            return False
        
        col_names = [col['name'] for col in columns]
        col_list = ', '.join([f"`{c}`" for c in col_names])
        new_col_list = ', '.join([f"NEW.`{c}`" for c in col_names])
        primary_keys = [col['name'] for col in columns if col['is_primary']]
        
        if not primary_keys:
            print(f"  ✗ No primary key found for {source_database}.{table}, cannot create triggers")
            return False
        
        # Build WHERE clause for UPDATE/DELETE triggers
        where_clause = ' AND '.join([f"`{pk}` = OLD.`{pk}`" for pk in primary_keys])
        
        # Drop existing triggers if they exist
        for trigger_type in ['insert', 'update', 'delete']:
            trigger_name = f"{table}_{trigger_type}_trigger"
            try:
                cursor.execute(f"DROP TRIGGER IF EXISTS `{source_database}`.`{trigger_name}`")
            except:
                pass
        
        print(f"  Creating replication triggers for {source_database}.{table}...")
        
        # Prepare debug log statements if verbose mode is enabled
        debug_start_insert = ""
        debug_end_insert = ""
        debug_start_update = ""
        debug_end_update = ""
        debug_start_delete = ""
        debug_end_delete = ""
        
        if args.mariadb_verbose:
            debug_start_insert = f"SIGNAL SQLSTATE '01000' SET MESSAGE_TEXT = 'DEBUG: {table}_insert_trigger START';"
            debug_end_insert = f"SIGNAL SQLSTATE '01000' SET MESSAGE_TEXT = 'DEBUG: {table}_insert_trigger END';"
            debug_start_update = f"SIGNAL SQLSTATE '01000' SET MESSAGE_TEXT = 'DEBUG: {table}_update_trigger START';"
            debug_end_update = f"SIGNAL SQLSTATE '01000' SET MESSAGE_TEXT = 'DEBUG: {table}_update_trigger END';"
            debug_start_delete = f"SIGNAL SQLSTATE '01000' SET MESSAGE_TEXT = 'DEBUG: {table}_delete_trigger START';"
            debug_end_delete = f"SIGNAL SQLSTATE '01000' SET MESSAGE_TEXT = 'DEBUG: {table}_delete_trigger END';"
        
        # Create INSERT trigger with proper delimiter
        cursor.execute("DELIMITER $$")
        insert_trigger = f"""
CREATE TRIGGER `{source_database}`.`{table}_insert_trigger`
AFTER INSERT ON `{source_database}`.`{table}`
FOR EACH ROW
BEGIN
    {debug_start_insert}
    INSERT INTO `{scylla_database}`.`{table}` ({col_list})
    VALUES ({new_col_list});
    {debug_end_insert}
END$$
        """
        cursor.execute(insert_trigger)
        cursor.execute("DELIMITER ;")
        print(f"    ✓ INSERT trigger created")
        
        # Create UPDATE trigger with UPDATE statement
        update_col_list = ', '.join([f"`{c}` = NEW.`{c}`" for c in col_names])
        cursor.execute("DELIMITER $$")
        update_trigger = f"""
CREATE TRIGGER `{source_database}`.`{table}_update_trigger`
AFTER UPDATE ON `{source_database}`.`{table}`
FOR EACH ROW
BEGIN
    {debug_start_update}
    UPDATE `{scylla_database}`.`{table}`
    SET {update_col_list}
    WHERE {where_clause};
    {debug_end_update}
END$$
        """
        cursor.execute(update_trigger)
        cursor.execute("DELIMITER ;")
        print(f"    ✓ UPDATE trigger created")
        
        # Create DELETE trigger with proper delimiter
        cursor.execute("DELIMITER $$")
        delete_trigger = f"""
CREATE TRIGGER `{source_database}`.`{table}_delete_trigger`
AFTER DELETE ON `{source_database}`.`{table}`
FOR EACH ROW
BEGIN
    {debug_start_delete}
    DELETE FROM `{scylla_database}`.`{table}` WHERE {where_clause};
    {debug_end_delete}
END$$
        """
        cursor.execute(delete_trigger)
        cursor.execute("DELIMITER ;")
        print(f"    ✓ DELETE trigger created")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error creating triggers for {source_database}.{table}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cursor.close()


def setup_table_migration(mariadb_conn, scylla_session, table_name, args):
    """
    Setup migration for a single table.
    
    Args:
        mariadb_conn: MariaDB connection
        scylla_session: ScyllaDB session
        table_name: Name of the table to migrate
        args: Command-line arguments
    """
    # Get table structure from MariaDB
    cursor = mariadb_conn.cursor(dictionary=True)
    try:
        print(f"  Getting table structure for '{table_name}'...")
        cursor.execute(f"SHOW FULL COLUMNS FROM `{args.mariadb_database}`.`{table_name}`")
        columns = cursor.fetchall()
        
        # Get primary key
        cursor.execute(f"""
            SELECT column_name
            FROM information_schema.key_column_usage
            WHERE table_schema = '{args.mariadb_database}'
            AND table_name = '{table_name}'
            AND constraint_name = 'PRIMARY'
            ORDER BY ordinal_position
        """)
        pk_columns = [row['column_name'] for row in cursor.fetchall()]
        
        if not pk_columns:
            print(f"  ✗ Error: Table '{table_name}' has no primary key")
            print(f"    ScyllaDB requires a primary key. Skipping this table.")
            return
        
        # Create ScyllaDB keyspace if it doesn't exist
        create_keyspace(scylla_session, args.scylla_ks)
        
        # Build and execute CREATE TABLE in ScyllaDB
        create_scylla_table(scylla_session, table_name, columns, pk_columns, args.scylla_ks)
        
        # Create ScyllaDB-backed table in MariaDB scylla_database
        create_mariadb_scylla_table(mariadb_conn, args.mariadb_database, args.mariadb_scylla_database, 
                                    args.scylla_ks, args.scylla_fdw_host, args.scylla_port, table_name, args)
        
        # Create triggers to replicate changes
        create_replication_triggers(mariadb_conn, args.mariadb_database, args.mariadb_scylla_database, table_name, args)
        
    finally:
        cursor.close()


def create_keyspace(session, keyspace):
    """Create ScyllaDB keyspace if it doesn't exist."""
    try:
        session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {keyspace}
            WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
        """)
        print(f"    ✓ Keyspace '{keyspace}' ready")
    except Exception as e:
        print(f"    ✗ Error creating keyspace: {e}")
        raise


def mariadb_type_to_cql_type(mariadb_type):
    """Convert MariaDB data type to CQL data type."""
    type_mapping = {
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
        'tinytext': 'text',
        'mediumtext': 'text',
        'longtext': 'text',
        'varbinary': 'blob',
        'binary': 'blob',
        'blob': 'blob',
        'tinyblob': 'blob',
        'mediumblob': 'blob',
        'longblob': 'blob',
        'date': 'date',
        'datetime': 'timestamp',
        'timestamp': 'timestamp',
        'time': 'time',
    }
    
    mariadb_type_lower = mariadb_type.lower()
    
    # Handle types with parameters (e.g., varchar(100) -> varchar)
    base_type = mariadb_type_lower.split('(')[0]
    
    # Check for exact or prefix match, but prioritize longer matches first
    # Sort by length descending to match 'timestamp' before 'time'
    for key in sorted(type_mapping.keys(), key=len, reverse=True):
        if base_type.startswith(key):
            return type_mapping[key]
    
    # Check for UUID (stored as BINARY(16) or CHAR(36) in MariaDB)
    if 'binary(16)' in mariadb_type_lower or 'char(36)' in mariadb_type_lower:
        return 'uuid'
    
    # Default to text for unknown types
    print(f"    ⚠ Warning: Unknown type '{mariadb_type}', using 'text'")
    return 'text'


def create_scylla_table(session, table_name, columns, pk_columns, keyspace):
    """Create table in ScyllaDB."""
    try:
        print(f"    Creating ScyllaDB table '{keyspace}.{table_name}'...")
        
        # Build column definitions
        col_defs = []
        for col in columns:
            col_name = col['Field']
            col_type = col['Type']
            cql_type = mariadb_type_to_cql_type(col_type)
            col_defs.append(f"{col_name} {cql_type}")
        
        # Build primary key
        pk_def = f"PRIMARY KEY ({', '.join(pk_columns)})"
        
        # Build CREATE TABLE statement
        cql = f"""
            CREATE TABLE IF NOT EXISTS {keyspace}.{table_name} (
                {', '.join(col_defs)},
                {pk_def}
            )
        """
        
        session.execute(cql)
        print(f"    ✓ ScyllaDB table created")
        
    except Exception as e:
        print(f"    ✗ Error creating ScyllaDB table: {e}")
        raise


def configure_mariadb_table(conn, table_name, args):
    """
    DEPRECATED: This function is no longer used.
    We now create a separate ScyllaDB-backed table instead of converting the original.
    """
    pass


def migrate_table_data(conn, source_database, scylla_database, table_name):
    """
    Migrate existing data from source table to ScyllaDB-backed table.
    
    Args:
        conn: MariaDB connection
        source_database: Source database name
        scylla_database: ScyllaDB-backed database name
        table_name: Name of the table to migrate
    """
    cursor = conn.cursor()
    try:
        print(f"\n  Migrating existing data for table '{table_name}'...")
        
        # Get row count from source table
        cursor.execute(f"SELECT COUNT(*) FROM `{source_database}`.`{table_name}`")
        row_count = cursor.fetchone()[0]
        
        if row_count == 0:
            print(f"    ⚠ No data in source table (table is empty)")
            return
        
        print(f"    Copying {row_count} row(s) from {source_database}.{table_name} to {scylla_database}.{table_name}...")
        
        # Copy data using INSERT...SELECT
        cursor.execute(f"""
            INSERT INTO `{scylla_database}`.`{table_name}`
            SELECT * FROM `{source_database}`.`{table_name}`
        """)
        
        print(f"    ✓ Migrated {row_count} row(s) to ScyllaDB")
        
    except Exception as e:
        print(f"    ✗ Error migrating table data: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()


if __name__ == "__main__":
    main()
