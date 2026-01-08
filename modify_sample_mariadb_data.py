#!/usr/bin/env python3
"""
Modify sample MariaDB data to test replication to ScyllaDB.
Performs INSERT, UPDATE, and DELETE operations on the sample tables.
"""

import argparse
import sys
import random
from datetime import datetime, timedelta
import mariadb


def main():
    """Main function to modify sample data."""
    args = parse_arguments()
    
    print("=" * 70)
    print("Modifying Sample MariaDB Data")
    print("=" * 70)
    
    # Connect to MariaDB
    try:
        conn = mariadb.connect(
            host=args.mariadb_host,
            port=args.mariadb_port,
            user=args.mariadb_user,
            password=args.mariadb_password,
            database=args.mariadb_database
        )
        print(f"\n✓ Connected to MariaDB at {args.mariadb_host}:{args.mariadb_port}")
    except Exception as e:
        print(f"\n✗ Failed to connect to MariaDB: {e}")
        sys.exit(1)
    
    # Perform operations
    print(f"\n{'=' * 70}")
    print("Cleaning up existing test data...")
    print("=" * 70)
    cleanup_test_data(conn)
    
    print(f"\n{'=' * 70}")
    print("Performing INSERT operations...")
    print("=" * 70)
    insert_operations(conn)
    
    print(f"\n{'=' * 70}")
    print("Performing UPDATE operations...")
    print("=" * 70)
    update_operations(conn)
    
    print(f"\n{'=' * 70}")
    print("Performing DELETE operations...")
    print("=" * 70)
    delete_operations(conn)
    
    # Cleanup
    conn.close()
    
    print(f"\n{'=' * 70}")
    print("✓ All modifications completed!")
    print("=" * 70)
    print("\nTo verify replication:")
    print(f"  Source (testdb):  SELECT * FROM {args.mariadb_database}.animals WHERE animal_id >= 10000;")
    print(f"  ScyllaDB (MariaDB view): SELECT * FROM scylla_db.animals WHERE animal_id >= 10000;")
    print(f"  ScyllaDB (direct): docker exec -it scylladb-migration-target cqlsh -e \"SELECT * FROM {args.scylla_ks}.animals WHERE animal_id >= 10000 ALLOW FILTERING;\"")


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Modify sample MariaDB data to test replication",
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
                              help='MariaDB database')
    
    # ScyllaDB options
    scylla_group = parser.add_argument_group('ScyllaDB options')
    scylla_group.add_argument('--scylla-ks', default='migration',
                              help='ScyllaDB keyspace name')
    
    return parser.parse_args()


def cleanup_test_data(conn):
    """Clean up any existing test data from previous runs."""
    cursor = conn.cursor()
    
    try:
        # Delete test data (IDs 10000-10999)
        print("\n[1/4] Cleaning up test animals...")
        cursor.execute("DELETE FROM animals WHERE animal_id >= 10000 AND animal_id < 11000")
        print(f"  ✓ Cleaned up test animals")
        
        print("\n[2/4] Cleaning up test habitats...")
        cursor.execute("DELETE FROM habitats WHERE habitat_id >= 10000 AND habitat_id < 11000")
        print(f"  ✓ Cleaned up test habitats")
        
        print("\n[3/4] Cleaning up test feedings...")
        cursor.execute("DELETE FROM feedings WHERE feeding_id >= 10000 AND feeding_id < 11000")
        print(f"  ✓ Cleaned up test feedings")
        
        print("\n[4/4] Cleaning up test equipment...")
        cursor.execute("DELETE FROM equipment WHERE equipment_id >= 10000 AND equipment_id < 11000")
        print(f"  ✓ Cleaned up test equipment")
        
        conn.commit()
        
    except Exception as e:
        print(f"  ⚠ Warning during cleanup: {e}")
        conn.rollback()
    finally:
        cursor.close()


def insert_operations(conn):
    """Perform INSERT operations on sample tables."""
    cursor = conn.cursor()
    
    try:
        # Insert new animals
        print("\n[1/3] Inserting new animals...")
        animals_data = [
            (10001, 'Test Lion', 'Lion', 5, 190.5, 'Savanna', '2026-01-04'),
            (10002, 'Test Tiger', 'Tiger', 3, 180.0, 'Forest', '2026-01-04'),
            (10003, 'Test Bear', 'Bear', 8, 250.3, 'Forest', '2026-01-04'),
        ]
        
        for animal in animals_data:
            try:
                cursor.execute(
                    "INSERT INTO animals (animal_id, name, species, age, weight_kg, habitat_name, last_checkup) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    animal
                )
                print(f"  ✓ Inserted animal: {animal[1]} (ID: {animal[0]})")
            except Exception as e:
                print(f"  ✗ Failed to insert animal {animal[1]}: {e}")
        
        # Insert new habitats
        print("\n[2/3] Inserting new habitats...")
        habitats_data = [
            (10001, 'Test Savanna Zone', 'Tropical', 150.5, 25, '2026-01-04'),
            (10002, 'Test Arctic Zone', 'Arctic', 200.0, 15, '2026-01-04'),
        ]
        
        for habitat in habitats_data:
            try:
                cursor.execute(
                    "INSERT INTO habitats (habitat_id, name, climate, size_acres, capacity, built_date) VALUES (?, ?, ?, ?, ?, ?)",
                    habitat
                )
                print(f"  ✓ Inserted habitat: {habitat[1]} (ID: {habitat[0]})")
            except Exception as e:
                print(f"  ✗ Failed to insert habitat {habitat[1]}: {e}")
        
        # Insert new feedings
        print("\n[3/3] Inserting new feedings...")
        feedings_data = [
            (10001, 'Test Lion', 'Meat', 15.0, datetime.now(), 'Test Keeper'),
            (10002, 'Test Tiger', 'Meat', 12.5, datetime.now(), 'Test Keeper'),
        ]
        
        for feeding in feedings_data:
            try:
                cursor.execute(
                    "INSERT INTO feedings (feeding_id, animal_name, food_type, quantity_kg, feeding_time, fed_by) VALUES (?, ?, ?, ?, ?, ?)",
                    feeding
                )
                print(f"  ✓ Inserted feeding: {feeding[1]} - {feeding[2]} (ID: {feeding[0]})")
            except Exception as e:
                print(f"  ✗ Failed to insert feeding for {feeding[1]}: {e}")
        
        conn.commit()
        
    except Exception as e:
        print(f"  ✗ Error during insert operations: {e}")
        conn.rollback()
    finally:
        cursor.close()


def update_operations(conn):
    """Perform UPDATE operations on sample tables."""
    cursor = conn.cursor()
    
    try:
        # Update animals
        print("\n[1/3] Updating animals...")
        cursor.execute("UPDATE animals SET weight_kg = 195.0 WHERE animal_id = 10001")
        print(f"  ✓ Updated animal weight (ID: 10001)")
        
        # Update habitats
        print("\n[2/3] Updating habitats...")
        cursor.execute("UPDATE habitats SET capacity = 30 WHERE habitat_id = 10001")
        print(f"  ✓ Updated habitat capacity (ID: 10001)")
        
        # Update feedings
        print("\n[3/3] Updating feedings...")
        cursor.execute("UPDATE feedings SET quantity_kg = 18.0 WHERE feeding_id = 10001")
        print(f"  ✓ Updated feeding quantity (ID: 10001)")
        
        conn.commit()
        
    except Exception as e:
        print(f"  ✗ Error during update operations: {e}")
        conn.rollback()
    finally:
        cursor.close()


def delete_operations(conn):
    """Perform DELETE operations on sample tables."""
    cursor = conn.cursor()
    
    try:
        # Delete feedings first (no foreign keys, but logical order)
        print("\n[1/3] Deleting feedings...")
        cursor.execute("DELETE FROM feedings WHERE feeding_id = 10002")
        print(f"  ✓ Deleted feeding (ID: 10002)")
        
        # Delete animals
        print("\n[2/3] Deleting animals...")
        cursor.execute("DELETE FROM animals WHERE animal_id = 10003")
        print(f"  ✓ Deleted animal (ID: 10003)")
        
        # Delete habitats
        print("\n[3/3] Deleting habitats...")
        cursor.execute("DELETE FROM habitats WHERE habitat_id = 10002")
        print(f"  ✓ Deleted habitat (ID: 10002)")
        
        conn.commit()
        
    except Exception as e:
        print(f"  ✗ Error during delete operations: {e}")
        conn.rollback()
    finally:
        cursor.close()


if __name__ == "__main__":
    main()
