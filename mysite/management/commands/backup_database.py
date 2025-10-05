"""
Management command to backup the database.

Usage:
    python manage.py backup_database
    python manage.py backup_database --output /path/to/backup.sql
    python manage.py backup_database --compress
"""
import os
import subprocess
import gzip
import shutil
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Backup the database to a file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path for the backup',
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress the backup with gzip',
        )
        parser.add_argument(
            '--backup-dir',
            type=str,
            default=str(Path(settings.BASE_DIR) / 'backups'),
            help='Directory to store backups (default: project_root/backups)',
        )

    def handle(self, *args, **options):
        """Execute the backup command."""
        # Create backup directory if it doesn't exist
        backup_dir = Path(options['backup_dir'])
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Determine output filename
        if options['output']:
            output_file = Path(options['output'])
        else:
            db_name = self._get_database_name()
            output_file = backup_dir / f'backup_{db_name}_{timestamp}.sql'

        # Add .gz extension if compressing
        if options['compress']:
            output_file = Path(str(output_file) + '.gz')

        try:
            self.stdout.write(f'Starting database backup...')
            self.stdout.write(f'Output file: {output_file}')

            # Get database configuration
            db_config = settings.DATABASES['default']
            db_engine = db_config['ENGINE']

            if 'postgresql' in db_engine:
                self._backup_postgresql(db_config, output_file, options['compress'])
            elif 'sqlite' in db_engine:
                self._backup_sqlite(db_config, output_file, options['compress'])
            else:
                raise CommandError(f'Unsupported database engine: {db_engine}')

            # Get file size
            file_size = output_file.stat().st_size / (1024 * 1024)  # MB

            self.stdout.write(
                self.style.SUCCESS(
                    f'Database backup completed successfully!\n'
                    f'File: {output_file}\n'
                    f'Size: {file_size:.2f} MB'
                )
            )

            logger.info(f'Database backup created: {output_file} ({file_size:.2f} MB)')

        except Exception as e:
            logger.error(f'Database backup failed: {e}')
            raise CommandError(f'Backup failed: {e}')

    def _get_database_name(self):
        """Get the database name from configuration."""
        db_config = settings.DATABASES['default']
        if 'NAME' in db_config:
            return Path(db_config['NAME']).stem if 'sqlite' in db_config['ENGINE'] else db_config['NAME']
        return 'database'

    def _backup_postgresql(self, db_config, output_file, compress):
        """Backup PostgreSQL database using pg_dump."""
        try:
            # Build pg_dump command
            cmd = [
                'pg_dump',
                '--no-owner',
                '--no-acl',
                '--clean',
                '--if-exists',
            ]

            # Add connection parameters
            env = os.environ.copy()
            if 'HOST' in db_config:
                cmd.extend(['--host', db_config['HOST']])
            if 'PORT' in db_config:
                cmd.extend(['--port', str(db_config['PORT'])])
            if 'USER' in db_config:
                cmd.extend(['--username', db_config['USER']])
            if 'PASSWORD' in db_config:
                env['PGPASSWORD'] = db_config['PASSWORD']

            # Add database name
            cmd.append(db_config['NAME'])

            self.stdout.write('Running pg_dump...')

            if compress:
                # Pipe directly to gzip
                with gzip.open(output_file, 'wb') as f:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env
                    )
                    stdout, stderr = process.communicate()

                    if process.returncode != 0:
                        raise CommandError(f'pg_dump failed: {stderr.decode()}')

                    f.write(stdout)
            else:
                # Write to file directly
                with open(output_file, 'wb') as f:
                    process = subprocess.Popen(
                        cmd,
                        stdout=f,
                        stderr=subprocess.PIPE,
                        env=env
                    )
                    _, stderr = process.communicate()

                    if process.returncode != 0:
                        raise CommandError(f'pg_dump failed: {stderr.decode()}')

        except FileNotFoundError:
            raise CommandError(
                'pg_dump not found. Please install PostgreSQL client tools.'
            )

    def _backup_sqlite(self, db_config, output_file, compress):
        """Backup SQLite database by copying the file."""
        db_path = Path(db_config['NAME'])

        if not db_path.exists():
            raise CommandError(f'Database file not found: {db_path}')

        self.stdout.write(f'Copying SQLite database file...')

        if compress:
            # Compress while copying
            with open(db_path, 'rb') as f_in:
                with gzip.open(output_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            # Direct copy
            shutil.copy2(db_path, output_file)
