#!/usr/bin/env python3
"""
Start and manage MariaDB and ScyllaDB containers for migration testing.
"""

import argparse
import os
import sys
import time
import subprocess
import docker
from docker.errors import NotFound, APIError, ImageNotFound


def ensure_network(client, network_name):
    """Create Docker network if it doesn't exist."""
    try:
        network = client.networks.get(network_name)
        print(f"  ℹ Network '{network_name}' already exists")
        return network
    except NotFound:
        print(f"  Creating network '{network_name}'...")
        network = client.networks.create(network_name, driver="bridge")
        print(f"  ✓ Network '{network_name}' created")
        return network


def query_mariadb_tags():
    """Query available MariaDB tags from GitHub."""
    try:
        result = subprocess.run(
            ['git', 'ls-remote', '--tags', 'https://github.com/MariaDB/server.git'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            print(f"  ✗ Error querying git tags: {result.stderr}")
            return []
        
        tags = []
        for line in result.stdout.split('\n'):
            if 'refs/tags/mariadb-' in line:
                # Extract tag name (e.g., mariadb-10.5.9)
                tag = line.split('refs/tags/')[-1].strip()
                # Remove ^{} suffix if present
                if tag.endswith('^{}'):
                    tag = tag[:-3]
                if tag.startswith('mariadb-'):
                    tags.append(tag)
        return tags
    except subprocess.TimeoutExpired:
        print("  ✗ Error: git ls-remote timed out")
        return []
    except FileNotFoundError:
        print("  ✗ Error: git command not found")
        return []
    except Exception as e:
        print(f"  ✗ Error querying tags: {e}")
        return []


def parse_version(version_str):
    """Parse version string into tuple of integers for comparison."""
    try:
        parts = version_str.replace('mariadb-', '').split('.')
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return None


def resolve_mariadb_version(version_spec):
    """Resolve MariaDB version specification to full X.Y.Z version.
    
    Args:
        version_spec: Either X.Y (find latest Z) or X.Y.Z (use as-is)
    
    Returns:
        Full version string X.Y.Z or None if not found
    """
    parts = version_spec.split('.')
    
    # If 3-digit version provided, verify it exists
    if len(parts) == 3:
        print(f"  Looking for MariaDB version {version_spec}...")
        tags = query_mariadb_tags()
        target_tag = f"mariadb-{version_spec}"
        if target_tag in tags:
            print(f"  ✓ Found version {version_spec}")
            return version_spec
        else:
            print(f"  ✗ Version {version_spec} not found")
            return None
    
    # If 2-digit version provided, find latest Z
    elif len(parts) == 2:
        major, minor = parts
        print(f"  Looking for latest MariaDB {major}.{minor}.x version...")
        tags = query_mariadb_tags()
        
        # Filter tags matching X.Y.* pattern
        matching_tags = []
        prefix = f"mariadb-{major}.{minor}."
        for tag in tags:
            if tag.startswith(prefix):
                version_tuple = parse_version(tag)
                if version_tuple and len(version_tuple) == 3:
                    matching_tags.append((tag, version_tuple))
        
        if not matching_tags:
            print(f"  ✗ No versions found matching {major}.{minor}.x")
            return None
        
        # Find max version using semantic version comparison
        latest_tag, latest_version = max(matching_tags, key=lambda x: x[1])
        version_str = '.'.join(map(str, latest_version))
        print(f"  ✓ Found latest version: {version_str}")
        return version_str
    
    else:
        print(f"  ✗ Invalid version format: {version_spec} (expected X.Y or X.Y.Z)")
        return None


def main():
    """Main function to start and manage database containers."""
    args = parse_arguments()
    
    # Resolve MariaDB version
    print("Resolving MariaDB version...")
    mariadb_version = resolve_mariadb_version(args.mariadb_version)
    if not mariadb_version:
        print(f"\n✗ Failed to resolve MariaDB version '{args.mariadb_version}'")
        sys.exit(1)
    print()
    
    try:
        client = docker.from_env()
    except Exception as e:
        print(f"Error connecting to Docker with default settings: {e}")
        print("\nTrying alternative Docker socket locations...")
        
        # Try common Docker socket locations on macOS
        socket_locations = [
            "unix:///Users/geoffmontee/.colima/default/docker.sock",
            "unix:///var/run/docker.sock",
            "unix://~/.docker/run/docker.sock",
        ]
        
        client = None
        for socket_path in socket_locations:
            try:
                expanded_path = socket_path.replace("~", os.path.expanduser("~"))
                print(f"  Trying: {expanded_path}")
                client = docker.DockerClient(base_url=expanded_path)
                client.ping()
                print(f"  ✓ Connected successfully!")
                break
            except Exception as socket_error:
                print(f"  ✗ Failed: {socket_error}")
                continue
        
        if client is None:
            print("\nCould not connect to Docker daemon.")
            print("Make sure Docker (or Colima) is running.")
            print("\nYou can also set the DOCKER_HOST environment variable:")
            print("  export DOCKER_HOST=unix:///Users/geoffmontee/.colima/default/docker.sock")
            sys.exit(1)

    # Create shared network for container communication
    network_name = "migration-network"
    ensure_network(client, network_name)
    
    # Configuration
    mariadb_config = {
        "name": "mariadb-migration-source",
        "image": "mariadb-scylla:latest",
        "ports": {"3306/tcp": 3306},
        "environment": {
            "MYSQL_ROOT_PASSWORD": "rootpassword",
            "MYSQL_DATABASE": "testdb"
        },
        "detach": True,
        "remove": False,
        "network": network_name
    }

    scylla_config = {
        "name": "scylladb-migration-target",
        "image": "scylladb/scylla:2025.4",
        "ports": {
            "9042/tcp": 9042,
            "9142/tcp": 9142,
            "19042/tcp": 19042,
            "19142/tcp": 19142
        },
        "detach": True,
        "remove": False,
        "command": "--smp 1 --memory 400M --overprovisioned 1 --api-address 0.0.0.0",
        "network": network_name
    }

    # Check if MariaDB image needs to be built
    print("=" * 60)
    print("Checking MariaDB Image")
    print("=" * 60)
    
    try:
        client.images.get("mariadb-scylla:latest")
        if not args.rebuild:
            print("  ✓ MariaDB image 'mariadb-scylla:latest' found")
        else:
            print("  ⟳ Rebuilding MariaDB image as requested...")
            build_mariadb_image(client, mariadb_version)
    except ImageNotFound:
        print("  ℹ MariaDB image not found, building now...")
        print("  ⚠ This will take 15-30 minutes on first run")
        build_mariadb_image(client, mariadb_version)

    # Manage MariaDB container
    print("=" * 60)
    print("Managing MariaDB Container")
    print("=" * 60)
    manage_container(client, mariadb_config, db_type="mariadb")

    # Manage ScyllaDB container
    print("\n" + "=" * 60)
    print("Managing ScyllaDB Container")
    print("=" * 60)
    manage_container(client, scylla_config, db_type="scylla")

    # Print connection information
    print_connection_info()


def build_mariadb_image(client, mariadb_version):
    """Build MariaDB image from Dockerfile."""
    print(f"  Building MariaDB {mariadb_version} image with ScyllaDB storage engine...")
    print("  This may take 15-30 minutes...")
    
    # Check if Dockerfile exists
    dockerfile_path = os.path.join(os.getcwd(), "Dockerfile")
    if not os.path.exists(dockerfile_path):
        print(f"  ✗ Error: Dockerfile not found at {dockerfile_path}")
        sys.exit(1)
    
    try:
        # Build the image
        image, build_logs = client.images.build(
            path=os.getcwd(),
            tag="mariadb-scylla:latest",
            rm=True,
            buildargs={"MARIADB_VERSION": mariadb_version}
        )
        
        # Print last few lines of build output
        print("\n  Build output (last 10 lines):")
        log_lines = []
        for chunk in build_logs:
            if 'stream' in chunk:
                log_lines.append(chunk['stream'].strip())
        
        for line in log_lines[-10:]:
            if line:
                print(f"    {line}")
        
        print(f"  ✓ MariaDB image built successfully")
        
    except Exception as e:
        print(f"  ✗ Error building MariaDB image: {e}")
        sys.exit(1)


def manage_container(client, config, db_type=None):
    """Check if container exists, create or restart as needed."""
    container_name = config["name"]
    
    try:
        container = client.containers.get(container_name)
        status = container.status
        
        print(f"  Found existing container '{container_name}' (status: {status})")
        
        if status == "running":
            print(f"  ✓ Container is already running")
            
            # Wait for health check
            if db_type:
                wait_for_health(container, container_name, db_type)
            
            return container
        
        elif status in ["created", "exited"]:
            print(f"  ⟳ Starting existing container...")
            container.start()
            print(f"  ✓ Container started")
            
            # Wait for health check
            if db_type:
                wait_for_health(container, container_name, db_type)
            
            return container
        
    except NotFound:
        print(f"  Container '{container_name}' does not exist")
        return create_and_start_container(client, config, db_type)
    
    except Exception as e:
        print(f"  ✗ Error managing container: {e}")
        sys.exit(1)


def create_and_start_container(client, config, db_type=None):
    """Create and start a new container."""
    container_name = config["name"]
    
    print(f"  ⟳ Creating new container '{container_name}'...")
    
    try:
        # Pull image if needed
        image_name = config["image"]
        
        if "mariadb-scylla" not in image_name:
            try:
                client.images.get(image_name)
                print(f"  ✓ Image '{image_name}' already available")
            except ImageNotFound:
                print(f"  ⟳ Pulling image '{image_name}'...")
                client.images.pull(image_name)
                print(f"  ✓ Image pulled successfully")
        
        # Create and start container
        container = client.containers.run(**config)
        print(f"  ✓ Container '{container_name}' created and started")
        
        # Wait for health check
        if db_type:
            wait_for_health(container, container_name, db_type)
        
        return container
        
    except APIError as e:
        print(f"  ✗ Error creating container: {e}")
        sys.exit(1)


def wait_for_health(container, container_name, db_type=None):
    """Wait for container to be healthy."""
    print(f"  ⟳ Waiting for {container_name} to be ready...")
    
    if db_type == "mariadb":
        check_mariadb_health()
    elif db_type == "scylla":
        check_scylladb_health(container)
    else:
        time.sleep(5)
        print(f"  ✓ {container_name} is ready")


def check_mariadb_health():
    """Check if MariaDB is accepting connections."""
    max_attempts = 60
    attempt = 0
    
    while attempt < max_attempts:
        try:
            result = subprocess.run(
                ["mariadb", "-h", "127.0.0.1", "-u", "root", "-prootpassword", "-e", "SELECT 1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            
            if result.returncode == 0:
                print(f"  ✓ MariaDB is ready")
                return True
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        attempt += 1
        if attempt < max_attempts:
            time.sleep(2)
            if attempt % 5 == 0:
                print(f"    Still waiting... ({attempt}/{max_attempts})")
    
    print(f"  ⚠ Warning: MariaDB health check timed out")
    return False


def check_scylladb_health(container):
    """Check if ScyllaDB is ready."""
    max_attempts = 60
    attempt = 0
    
    print("  Waiting for ScyllaDB to start (this may take 30-60 seconds)...")
    
    while attempt < max_attempts:
        try:
            # Check if ScyllaDB is listening on CQL port
            result = container.exec_run(["nodetool", "status"])
            
            if result.exit_code == 0:
                output = result.output.decode('utf-8')
                if "UN" in output:  # UP and Normal
                    print(f"  ✓ ScyllaDB is ready")
                    return True
                    
        except Exception:
            pass
        
        attempt += 1
        if attempt < max_attempts:
            time.sleep(2)
            if attempt % 5 == 0:
                print(f"    Still waiting... ({attempt}/{max_attempts})")
    
    print(f"  ⚠ Warning: ScyllaDB health check timed out")
    return False


def print_connection_info():
    """Print connection information for both databases."""
    print("\n" + "=" * 60)
    print("✓ Containers Started Successfully")
    print("=" * 60)
    
    print("\nConnection Information:")
    print("\n  MariaDB:")
    print("    Host: 127.0.0.1")
    print("    Port: 3306")
    print("    User: root")
    print("    Password: rootpassword")
    print("    Database: testdb")
    print("    CLI: mariadb -h 127.0.0.1 -u root -prootpassword testdb")
    
    print("\n  ScyllaDB:")
    print("    Host: localhost")
    print("    Port: 9042")
    print("    CLI: docker exec -it scylladb-migration-target cqlsh")
    
    print("\nNext Steps:")
    print("  1. Load sample schema: mariadb -h 127.0.0.1 -u root -prootpassword testdb < sample_mariadb_schema.sql")
    print("  2. Load sample data: mariadb -h 127.0.0.1 -u root -prootpassword testdb < sample_mariadb_data.sql")
    print("  3. Setup migration: python3 setup_migration.py")
    print("  4. Test replication: python3 modify_sample_mariadb_data.py")
    print()


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Start MariaDB and ScyllaDB containers for migration testing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument('--rebuild', action='store_true',
                        help='Force rebuild of MariaDB Docker image')
    parser.add_argument('--mariadb-version', default='12.1',
                        help='MariaDB version to build (X.Y for latest X.Y.Z, or X.Y.Z for specific version)')
    
    return parser.parse_args()


if __name__ == "__main__":
    main()
