#!/usr/bin/env python3
"""
Incrementally copy loinc_pg_embedding table from local PostgreSQL to RDS via SSM tunnel.
Copies data in batches to avoid connection timeouts with large datasets.
"""

import argparse
import subprocess
import sys
import time
import signal
import psycopg2
from psycopg2.extras import execute_values, Json
from psycopg2.extensions import register_adapter
import boto3
import logging
from tqdm import tqdm

# Register JSON adapter for dict objects
register_adapter(dict, Json)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SSMTunnel:
    """Manages AWS SSM port forwarding session"""
    
    def __init__(self, instance_id, remote_host, remote_port, local_port, aws_profile='zivohealth'):
        self.instance_id = instance_id
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.local_port = local_port
        self.aws_profile = aws_profile
        self.process = None
    
    def start(self):
        """Start SSM port forwarding session"""
        logger.info(f"Starting SSM tunnel: localhost:{self.local_port} -> {self.remote_host}:{self.remote_port}")
        
        cmd = [
            'aws', 'ssm', 'start-session',
            '--target', self.instance_id,
            '--document-name', 'AWS-StartPortForwardingSessionToRemoteHost',
            '--parameters', f'{{"host":["{self.remote_host}"],"portNumber":["{self.remote_port}"],"localPortNumber":["{self.local_port}"]}}',
            '--profile', self.aws_profile
        ]
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        logger.info(f"SSM session started (PID: {self.process.pid})")
        
        # Wait for tunnel to be ready
        logger.info("Waiting for tunnel to be ready...")
        max_wait = 30
        for i in range(max_wait):
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', self.local_port))
                sock.close()
                if result == 0:
                    logger.info("✓ Tunnel is ready!")
                    time.sleep(2)  # Extra buffer
                    return True
            except Exception:
                pass
            
            time.sleep(1)
            if (i + 1) % 5 == 0:
                logger.info(f"   Still waiting... ({i+1}/{max_wait} seconds)")
        
        logger.error("Tunnel failed to establish")
        return False
    
    def stop(self):
        """Stop SSM port forwarding session"""
        if self.process:
            logger.info("Stopping SSM tunnel...")
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            
            # Also kill any remaining SSM processes
            subprocess.run(
                ['pkill', '-f', f'start-session.*{self.instance_id}'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logger.info("✓ SSM tunnel closed")


class IncrementalTableCopy:
    """Handles incremental table copying between databases"""
    
    def __init__(self, source_params, target_params, table_name, batch_size=500):
        self.source_params = source_params
        self.target_params = target_params
        self.table_name = table_name
        self.batch_size = batch_size
        self.source_conn = None
        self.target_conn = None
    
    def connect(self):
        """Establish database connections"""
        logger.info(f"Connecting to source database at {self.source_params['host']}...")
        self.source_conn = psycopg2.connect(**self.source_params)
        
        logger.info(f"Connecting to target database at {self.target_params['host']}...")
        self.target_conn = psycopg2.connect(**self.target_params)
        
        logger.info("✓ Database connections established")
    
    def disconnect(self):
        """Close database connections"""
        if self.source_conn:
            self.source_conn.close()
        if self.target_conn:
            self.target_conn.close()
        logger.info("Database connections closed")
    
    def get_table_info(self):
        """Get table structure and row count"""
        with self.source_conn.cursor() as cursor:
            # Get column names and types
            cursor.execute(f"""
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = '{self.table_name}'
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name};")
            row_count = cursor.fetchone()[0]
            
            return columns, row_count
    
    def get_primary_key(self):
        """Get the primary key column name"""
        with self.source_conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = '{self.table_name}'::regclass AND i.indisprimary;
            """)
            result = cursor.fetchone()
            return result[0] if result else 'uuid'  # Default to uuid if not found
    
    def copy_data(self, truncate_target=False):
        """Copy data incrementally in batches with progress bar"""
        try:
            # Get table info
            columns, total_rows = self.get_table_info()
            column_names = [col[0] for col in columns]
            pk_column = self.get_primary_key()
            
            logger.info(f"Table: {self.table_name}")
            logger.info(f"Columns: {len(column_names)} ({', '.join(column_names[:5])}...)")
            logger.info(f"Primary Key: {pk_column}")
            logger.info(f"Total rows to copy: {total_rows:,}")
            
            if total_rows == 0:
                logger.warning("Source table is empty. Nothing to copy.")
                return True
            
            # Truncate target if requested
            if truncate_target:
                logger.info("Truncating target table...")
                with self.target_conn.cursor() as cursor:
                    cursor.execute(f"TRUNCATE TABLE {self.table_name} CASCADE;")
                    self.target_conn.commit()
                logger.info("✓ Target table truncated")
            
            # Get initial target count
            with self.target_conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {self.table_name};")
                initial_count = cursor.fetchone()[0]
            
            logger.info(f"Target table has {initial_count:,} rows before copy")
            logger.info(f"Starting incremental copy with batch size {self.batch_size}...")
            logger.info("=" * 60)
            
            # Copy data in batches with progress bar
            column_list = ', '.join([f'"{col}"' for col in column_names])
            total_copied = 0
            offset = 0
            
            # Create progress bar
            pbar = tqdm(
                total=total_rows,
                desc="Copying rows",
                unit="rows",
                unit_scale=True,
                ncols=100,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
            )
            
            try:
                while offset < total_rows:
                    # Fetch batch from source
                    with self.source_conn.cursor() as source_cursor:
                        query = f"""
                            SELECT {column_list}
                            FROM {self.table_name}
                            ORDER BY "{pk_column}"
                            LIMIT {self.batch_size}
                            OFFSET {offset};
                        """
                        source_cursor.execute(query)
                        rows = source_cursor.fetchall()
                    
                    if not rows:
                        break
                    
                    # Insert batch into target using execute_values (faster)
                    with self.target_conn.cursor() as target_cursor:
                        placeholders = ', '.join([f'"{col}"' for col in column_names])
                        insert_query = f"INSERT INTO {self.table_name} ({placeholders}) VALUES %s"
                        
                        execute_values(
                            target_cursor,
                            insert_query,
                            rows,
                            page_size=self.batch_size
                        )
                        self.target_conn.commit()
                    
                    total_copied += len(rows)
                    offset += self.batch_size
                    
                    # Update progress bar
                    pbar.update(len(rows))
                    
                    # Small delay to avoid overwhelming the connection
                    time.sleep(0.05)
            
            finally:
                pbar.close()
            
            logger.info("=" * 60)
            
            # Verify final counts
            with self.target_conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {self.table_name};")
                final_count = cursor.fetchone()[0]
            
            logger.info("Copy completed!")
            logger.info(f"Source rows: {total_rows:,}")
            logger.info(f"Target rows before: {initial_count:,}")
            logger.info(f"Target rows after: {final_count:,}")
            logger.info(f"Rows copied: {total_copied:,}")
            
            if truncate_target:
                success = final_count == total_rows
            else:
                success = (final_count - initial_count) == total_copied
            
            if success:
                logger.info("✅ Verification successful!")
            else:
                logger.warning("⚠️  Row counts don't match as expected")
            
            return success
            
        except Exception as e:
            logger.error(f"Error during copy: {e}")
            if self.target_conn:
                self.target_conn.rollback()
            raise


def get_aws_config(profile='zivohealth'):
    """Get AWS configuration from SSM and EC2"""
    session = boto3.Session(profile_name=profile)
    ec2 = session.client('ec2')
    ssm = session.client('ssm')
    
    logger.info("Getting AWS configuration...")
    
    # Get EC2 instance ID
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:Name', 'Values': ['*zivohealth*']},
            {'Name': 'instance-state-name', 'Values': ['running']}
        ]
    )
    instance_id = response['Reservations'][0]['Instances'][0]['InstanceId']
    
    # Get RDS credentials from SSM
    params = ssm.get_parameters(
        Names=[
            '/zivohealth/production/db/host',
            '/zivohealth/production/db/user',
            '/zivohealth/production/db/password'
        ],
        WithDecryption=True
    )
    
    config = {
        'instance_id': instance_id,
    }
    
    for param in params['Parameters']:
        name = param['Name'].split('/')[-1]
        config[name] = param['Value']
    
    logger.info(f"✓ EC2 Instance: {instance_id}")
    logger.info(f"✓ RDS Host: {config['host']}")
    
    return config


def main():
    parser = argparse.ArgumentParser(
        description='Incrementally copy loinc_pg_embedding table from local to RDS'
    )
    
    # Source database
    parser.add_argument('--source-host', default='localhost', help='Source DB host')
    parser.add_argument('--source-port', type=int, default=5432, help='Source DB port')
    parser.add_argument('--source-user', default='rajanishsd', help='Source DB user')
    parser.add_argument('--source-password', default='', help='Source DB password')
    parser.add_argument('--source-db', default='zivohealth', help='Source database name')
    
    # Target database
    parser.add_argument('--target-db', default='zivohealth_dev', help='Target database name')
    parser.add_argument('--forwarded-port', type=int, default=15432, help='Local port for SSM tunnel')
    
    # Copy options
    parser.add_argument('--table-name', default='loinc_pg_embedding', help='Table to copy')
    parser.add_argument('--batch-size', type=int, default=500, help='Rows per batch')
    parser.add_argument('--truncate', action='store_true', help='Truncate target before copy')
    parser.add_argument('--aws-profile', default='zivohealth', help='AWS profile')
    
    args = parser.parse_args()
    
    tunnel = None
    copier = None
    
    try:
        logger.info("=" * 60)
        logger.info("Incremental LOINC Table Copy: Local → RDS")
        logger.info("=" * 60)
        
        # Get AWS configuration
        aws_config = get_aws_config(args.aws_profile)
        
        # Start SSM tunnel
        tunnel = SSMTunnel(
            instance_id=aws_config['instance_id'],
            remote_host=aws_config['host'],
            remote_port=5432,
            local_port=args.forwarded_port,
            aws_profile=args.aws_profile
        )
        
        if not tunnel.start():
            logger.error("Failed to establish SSM tunnel")
            sys.exit(1)
        
        # Prepare connection parameters
        source_params = {
            'host': args.source_host,
            'port': args.source_port,
            'user': args.source_user,
            'database': args.source_db
        }
        if args.source_password:
            source_params['password'] = args.source_password
        
        target_params = {
            'host': 'localhost',
            'port': args.forwarded_port,
            'user': aws_config['user'],
            'password': aws_config['password'],
            'database': args.target_db
        }
        
        # Create copier and execute
        copier = IncrementalTableCopy(
            source_params,
            target_params,
            args.table_name,
            args.batch_size
        )
        
        copier.connect()
        success = copier.copy_data(truncate_target=args.truncate)
        
        if success:
            logger.info("=" * 60)
            logger.info("✅ Table copy completed successfully!")
            logger.info("=" * 60)
            sys.exit(0)
        else:
            logger.error("❌ Table copy completed with warnings")
            sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("\n⚠️  Copy interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup
        if copier:
            copier.disconnect()
        if tunnel:
            tunnel.stop()


if __name__ == '__main__':
    main()

