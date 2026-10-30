#!/usr/bin/env bash
# Executed inside one container, with an isolated PostgreSQL data directory.
set -euo pipefail
DEFAULT_DB_USER="$1"
shift
export PYTHONPATH="/pandora/src:/pandora${PYTHONPATH:+:$PYTHONPATH}"
export PGDATA=/pandora-run/pgdata
cd /pandora

# Read main.py's optional config using the Python installed in the container.
# Keep arguments intact, including filenames containing spaces.
python3 - "$DEFAULT_DB_USER" "$@" > /pandora-run/db-settings <<'PY'
import json
import socket
import sys

config = {}
args = sys.argv[3:]
for i, arg in enumerate(args):
    if arg in ('-c', '--config'):
        if i + 1 == len(args):
            raise SystemExit('Missing config filename')
        with open(args[i + 1]) as stream:
            config = json.load(stream)
        break
    if arg.startswith('--config='):
        with open(arg.split('=', 1)[1]) as stream:
            config = json.load(stream)
        break
if config.get('host') not in (None, '', 'localhost', '127.0.0.1', '::1'):
    raise SystemExit('This launcher starts a local database; config host must be localhost.')
if config.get('port'):
    port = int(config['port'])
else:
    # Other jobs can share a physical node. Let the OS select an unused port;
    # export it as PGPORT for Pandora and its child workers below.
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
if not 1 <= port <= 65535:
    raise SystemExit('Invalid PostgreSQL port')
values = [str(port), config.get('user') or sys.argv[1], config.get('database') or 'postgres']
for value in values:
    if not isinstance(value, str) or any(c in value for c in '\n\r\0'):
        raise SystemExit('Invalid database configuration value')
    print(value)
PY
mapfile -t DB_SETTINGS < /pandora-run/db-settings
export PGPORT="${DB_SETTINGS[0]}"
export PGUSER="${DB_SETTINGS[1]}"
DB_NAME="${DB_SETTINGS[2]}"
export PGHOST=127.0.0.1

initdb -D "$PGDATA" -U "$PGUSER" --auth-local=trust --auth-host=trust
cleanup() {
    pg_ctl -D "$PGDATA" -m fast -w stop || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Every worker opens a connection to this node's database.
MAX_CONNECTIONS=$(( ${PANDORA_WORKER_COUNT:-1} + 16 ))
if ((MAX_CONNECTIONS < 100)); then MAX_CONNECTIONS=100; fi
pg_ctl -D "$PGDATA" -l /pandora-run/postgres.log \
    -o "-p $PGPORT -k /pandora-run/pgrun -h localhost -c max_connections=$MAX_CONNECTIONS" -w start
if [[ "$DB_NAME" != postgres && "$DB_NAME" != template0 && "$DB_NAME" != template1 ]]; then
    createdb -- "$DB_NAME"
fi
python3 -u "$@"
