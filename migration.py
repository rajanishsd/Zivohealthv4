#!/usr/bin/env python3
"""
Chunked restore of a single table from a pg_restore dump to Postgres/RDS.

- Extracts only the table's COPY stream via pg_restore
- Streams rows to RDS in configurable chunk sizes
- Uses psql + libpq keepalives to reduce disconnects
- Does not require psycopg2

Example:
  python3 restore_table_chunks.py \
    --dump /Users/rajanishsd/Documents/ZivohealthPlatform/local_data.dump \
    --table public.loinc_pg_collection \
    --host <RDS_HOST> --port 5432 --dbname <DB> --user <USER> --password <PWD> \
    --sslmode require --chunk-size 200000 --truncate-before

Prereqs: pg_restore and psql available in PATH.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Iterator, Tuple


# Default configuration (overridable via CLI flags)
DEFAULTS = {
    "dump": "/Users/rajanishsd/Documents/ZivohealthPlatform/local_data.dump",
    "table": "public.loinc_pg_collection",
    "host": "localhost",
    "port": 5432,
    "dbname": "zivohealth_dev",
    "user": "zivo",
    "password": "zivo_890",
    "sslmode": "disable",  # for localhost
    "chunk_size": 100_000,
    "statement_timeout_ms": 0,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 10,
    "truncate_before": False,
    "truncate_cascade": False,
    "disable_triggers": False,
    "skip_predata": False,
}


def check_binaries() -> None:
    for bin_name in ("pg_restore", "psql"):
        try:
            subprocess.run([bin_name, "--version"], check=True, capture_output=True)
        except Exception as exc:
            raise RuntimeError(f"Required binary '{bin_name}' not found in PATH") from exc


def build_dsn(args: argparse.Namespace) -> str:
    parts = [
        f"host={args.host}",
        f"port={args.port}",
        f"dbname={args.dbname}",
        f"user={args.user}",
        f"password={args.password}",
        f"sslmode={args.sslmode}",
        "keepalives=1",
        f"keepalives_idle={args.keepalives_idle}",
        f"keepalives_interval={args.keepalives_interval}",
        f"keepalives_count={args.keepalives_count}",
    ]
    return " ".join(parts)


def extract_table_copy_sql(dump_path: str, table: str, out_sql_path: str) -> None:
    cmd = [
        "pg_restore",
        "-a",                 # data only
        "-t", table,          # only this table
        "-f", out_sql_path,   # write to file
        dump_path,
    ]
    subprocess.run(cmd, check=True)


def extract_table_inserts_sql(dump_path: str, table: str, out_sql_path: str) -> None:
    cmd = [
        "pg_restore",
        "-a",
        "--inserts",       # fall back to INSERT statements
        "-t", table,
        "-f", out_sql_path,
        dump_path,
    ]
    subprocess.run(cmd, check=True)


def parse_copy_header_and_rows(sql_path: str) -> Tuple[str, Iterator[str]]:
    """
    Returns:
      - copy_header: the single 'COPY ... FROM stdin;' line including semicolon
      - rows_iter: iterator over raw COPY data lines (without the final '\.')
    """
    def rows_generator() -> Iterator[str]:
        with open(sql_path, "r", encoding="utf-8", newline="") as f:
            in_copy = False
            copy_header_local = None
            for line in f:
                if not in_copy:
                    if line.startswith("COPY ") and " FROM stdin;" in line:
                        nonlocal_copy_header[0] = line.rstrip("\n")
                        in_copy = True
                    continue

                # in_copy == True
                if line.strip() == r"\.":
                    break
                yield line

        if nonlocal_copy_header[0] is None:
            raise RuntimeError("COPY header not found in extracted SQL")

    nonlocal_copy_header = [None]
    rows_iter = rows_generator()
    # We need to advance until header is found; generator sets it lazily
    # Prime the generator minimally
    try:
        first = next(rows_iter)
        # push back behavior: reconstruct a new generator that yields first then rest
        def new_rows_iter():
            yield first
            for r in rows_generator():
                yield r
        return nonlocal_copy_header[0], new_rows_iter()
    except StopIteration:
        # No data rows; ensure header was found
        if nonlocal_copy_header[0] is None:
            raise RuntimeError("COPY header not found in extracted SQL (empty file?)")
        # Empty table: return empty iterator
        def empty_iter():
            if False:
                yield ""  # pragma: no cover
        return nonlocal_copy_header[0], empty_iter()


def build_pg_env(args: argparse.Namespace, statement_timeout_ms: int) -> dict:
    env = os.environ.copy()
    env["PGHOST"] = str(args.host)
    env["PGPORT"] = str(args.port)
    env["PGDATABASE"] = str(args.dbname)
    env["PGUSER"] = str(args.user)
    env["PGPASSWORD"] = str(args.password)
    env["PGSSLMODE"] = str(args.sslmode)
    env["PGOPTIONS"] = f"-c statement_timeout={statement_timeout_ms} -c lock_timeout=0"
    return env


def run_psql_sql(dsn: str, sql_text: str, env: dict) -> None:
    # Use PG* env for connection; avoid passing DSN to psql to prevent parsing issues
    cmd = ["psql", "-v", "ON_ERROR_STOP=1", "-q", "-X"]
    subprocess.run(
        cmd,
        input=sql_text.encode("utf-8"),
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    

def run_psql_query(dsn: str, sql_text: str, env: dict) -> str:
    # Use PG* env for connection; avoid passing DSN to psql to prevent parsing issues
    cmd = ["psql", "-v", "ON_ERROR_STOP=1", "-t", "-A", "-q", "-X", "-c", sql_text]
    proc = subprocess.run(
        cmd,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stdout.decode("utf-8").strip()


def is_custom_dump(dump_path: str) -> bool:
    try:
        with open(dump_path, "rb") as f:
            magic = f.read(5)
        return magic == b"PGDMP"
    except Exception:
        return False


def _matches_copy_header(line: str, table: str) -> bool:
    if not line.startswith("COPY ") or " FROM stdin;" not in line:
        return False
    schema, name = split_schema_table(table)
    unquoted = f"COPY {schema}.{name} "
    quoted = f'COPY "{schema}"."{name}" '
    return line.startswith(unquoted) or line.startswith(quoted)


def file_contains_copy_for_table(sql_path: str, table: str) -> bool:
    try:
        with open(sql_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if _matches_copy_header(line, table):
                    return True
        return False
    except Exception:
        return False


def parse_insert_statements(sql_path: str, table: str) -> Iterator[str]:
    schema, name = split_schema_table(table)
    prefixes = [f"INSERT INTO {schema}.{name} ", f'INSERT INTO "{schema}"."{name}" ']
    buf = []
    in_insert = False
    with open(sql_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not in_insert:
                # Start of an INSERT for our table
                if any(line.startswith(p) for p in prefixes):
                    in_insert = True
                    buf = [line.rstrip("\n")]
                # else ignore other lines
                continue
            else:
                buf.append(line.rstrip("\n"))
                if line.rstrip().endswith(";"):
                    # End of this INSERT statement
                    yield "\n".join(buf)
                    buf = []
                    in_insert = False
        # If we exit while still in_insert, flush defensively
        if in_insert and buf:
            yield "\n".join(buf)


def execute_insert_batches(dsn: str, inserts_iter: Iterator[str], batch_size: int, env: dict) -> int:
    batch = []
    total = 0
    idx = 0
    def flush():
        nonlocal batch, total, idx
        if not batch:
            return
        idx += 1
        sql_text = "\n".join(batch) + "\n"
        run_psql_sql(dsn, sql_text, env)
        total += len(batch)
        print(f"Executed INSERT batch {idx} with {len(batch)} statements; total={total}")
        batch = []
    for stmt in inserts_iter:
        batch.append(stmt)
        if len(batch) >= batch_size:
            flush()
    flush()
    return total


def extract_copy_from_plain_dump(dump_path: str, table: str) -> Tuple[str, Iterator[str]]:
    def rows_from_plain() -> Iterator[str]:
        with open(dump_path, "r", encoding="utf-8", errors="ignore") as f:
            in_copy = False
            for line in f:
                if not in_copy:
                    if _matches_copy_header(line, table):
                        nonlocal_header[0] = line.rstrip("\n")
                        in_copy = True
                    continue
                if line.strip() == r"\.":
                    break
                yield line
        if nonlocal_header[0] is None:
            raise RuntimeError("COPY header not found for table in plain SQL dump")

    nonlocal_header = [None]
    gen = rows_from_plain()
    # Prime to ensure header is set
    try:
        first = next(gen)
        def again():
            yield first
            for r in rows_from_plain():
                yield r
        return nonlocal_header[0], again()
    except StopIteration:
        if nonlocal_header[0] is None:
            raise RuntimeError("COPY header not found for table in plain SQL dump (empty)")
        def empty():
            if False:
                yield ""
        return nonlocal_header[0], empty()


def chunked_copy_load(
    dsn: str,
    copy_header: str,
    rows_iter: Iterator[str],
    chunk_size: int,
    disable_triggers: bool,
    env: dict,
) -> int:
    """
    Streams rows in chunks into COPY.
    Returns total number of rows loaded.
    """
    buffer = []
    total = 0
    chunk_index = 0

    def flush():
        nonlocal buffer, total, chunk_index
        if not buffer:
            return
        chunk_index += 1
        sql_parts = []
        if disable_triggers:
            sql_parts.append("SET session_replication_role = 'replica';")
        sql_parts.append(copy_header)
        sql_parts.extend(buffer)
        sql_parts.append(r"\.")
        if disable_triggers:
            sql_parts.append("SET session_replication_role = 'origin';")
        sql_text = "\n".join(sql_parts) + "\n"
        run_psql_sql(dsn, sql_text, env)
        total += len(buffer)
        print(f"Loaded chunk {chunk_index} with {len(buffer)} rows; total={total}")
        buffer = []

    for row in rows_iter:
        buffer.append(row.rstrip("\n"))
        if len(buffer) >= chunk_size:
            flush()

    flush()
    return total


def maybe_truncate_table(dsn: str, table: str, cascade: bool, env: dict) -> None:
    cascade_sql = " CASCADE" if cascade else ""
    sql = f'TRUNCATE TABLE {table}{cascade_sql};'
    run_psql_sql(dsn, sql, env)
    print(f"Truncated {table}{' CASCADE' if cascade else ''}")


def quote_literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def split_schema_table(qualified: str) -> Tuple[str, str]:
    if "." not in qualified:
        return "public", qualified
    schema, name = qualified.split(".", 1)
    return schema, name


def table_exists(dsn: str, table: str, env: dict) -> bool:
    schema, name = split_schema_table(table)
    sql = (
        "SELECT 1 FROM information_schema.tables "
        f"WHERE table_schema = {quote_literal(schema)} AND table_name = {quote_literal(name)} LIMIT 1;"
    )
    out = run_psql_query(dsn, sql, env)
    return out.strip() == "1"


def restore_predata_for_table(dump_path: str, table: str, env: dict) -> None:
    cmd = [
        "pg_restore",
        "--section=pre-data",
        "--no-owner",
        "--no-privileges",
        "-t",
        table,
        "-d",
        env.get("PGDATABASE", ""),
        dump_path,
    ]
    subprocess.run(cmd, check=True, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunked restore for a single table from a pg_restore dump.")
    parser.add_argument("--dump", default=DEFAULTS["dump"], help="Path to custom-format dump (created by pg_dump -Fc)")
    parser.add_argument("--table", default=DEFAULTS["table"], help="Target table in schema.table form, e.g. public.loinc_pg_collection")

    # Connection
    parser.add_argument("--host", default=DEFAULTS["host"])
    parser.add_argument("--port", type=int, default=DEFAULTS["port"])
    parser.add_argument("--dbname", default=DEFAULTS["dbname"])
    parser.add_argument("--user", default=DEFAULTS["user"])
    parser.add_argument("--password", default=DEFAULTS["password"])
    parser.add_argument("--sslmode", default=DEFAULTS["sslmode"], choices=["disable", "allow", "prefer", "require", "verify-ca", "verify-full"])

    # Performance / reliability
    parser.add_argument("--chunk-size", type=int, default=DEFAULTS["chunk_size"], help="Rows per COPY chunk")
    parser.add_argument("--statement-timeout-ms", type=int, default=DEFAULTS["statement_timeout_ms"], help="0 means no timeout")
    parser.add_argument("--keepalives-idle", type=int, default=DEFAULTS["keepalives_idle"])
    parser.add_argument("--keepalives-interval", type=int, default=DEFAULTS["keepalives_interval"])
    parser.add_argument("--keepalives-count", type=int, default=DEFAULTS["keepalives_count"])

    # Options
    parser.add_argument("--truncate-before", action="store_true", default=DEFAULTS["truncate_before"], help="TRUNCATE the table before loading")
    parser.add_argument("--truncate-cascade", action="store_true", default=DEFAULTS["truncate_cascade"], help="Use CASCADE with TRUNCATE (if needed)")
    parser.add_argument("--disable-triggers", action="store_true", default=DEFAULTS["disable_triggers"], help="Use session_replication_role=replica per chunk")
    parser.add_argument("--skip-predata", action="store_true", default=DEFAULTS["skip_predata"], help="Skip automatic pre-data (schema) restore if table is missing")
    args = parser.parse_args()

    try:
        check_binaries()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if not shutil.which("pg_restore"):
        print("pg_restore not found in PATH", file=sys.stderr)
        sys.exit(1)
    if not shutil.which("psql"):
        print("psql not found in PATH", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(args.dump):
        print(f"Dump file not found: {args.dump}", file=sys.stderr)
        sys.exit(1)

    dsn = build_dsn(args)
    env = build_pg_env(args, args.statement_timeout_ms)

    with tempfile.TemporaryDirectory(prefix="chunked_restore_") as tmpdir:
        extracted_sql = os.path.join(tmpdir, "table_data.sql")

        # Ensure schema/table exists
        if not args.skip_predata and not table_exists(dsn, args.table, env):
            print(f"Table {args.table} not found; restoring pre-data (schema)...")
            restore_predata_for_table(args.dump, args.table, env)

        print(f"Extracting COPY stream for {args.table} from dump...")
        if is_custom_dump(args.dump):
            # First try COPY
            extract_table_copy_sql(args.dump, args.table, extracted_sql)
            if file_contains_copy_for_table(extracted_sql, args.table):
                print("Parsing COPY header and streaming rows (custom dump, COPY)...")
                copy_header, rows_iter = parse_copy_header_and_rows(extracted_sql)
                use_copy = True
            else:
                # Fall back to INSERT statements
                print("No COPY section found in custom dump output; falling back to INSERT extraction...")
                extract_table_inserts_sql(args.dump, args.table, extracted_sql)
                inserts_iter = parse_insert_statements(extracted_sql, args.table)
                use_copy = False
        else:
            print("Detected plain SQL dump; scanning for COPY section directly...")
            try:
                copy_header, rows_iter = extract_copy_from_plain_dump(args.dump, args.table)
                use_copy = True
            except RuntimeError:
                print("No COPY in plain dump; scanning for INSERT statements...")
                inserts_iter = parse_insert_statements(args.dump, args.table)
                use_copy = False
        if not copy_header:
            print("Failed to parse COPY header; aborting.", file=sys.stderr)
            sys.exit(1)

        # Optionally truncate
        if args.truncate_before:
            maybe_truncate_table(
                dsn, args.table, cascade=args.truncate_cascade, env=env
            )

        if 'use_copy' in locals() and use_copy:
            total_rows = chunked_copy_load(
                dsn=dsn,
                copy_header=copy_header,
                rows_iter=rows_iter,
                chunk_size=args.chunk_size,
                disable_triggers=args.disable_triggers,
                env=env,
            )
        else:
            # Execute INSERT statements in batches (batch_size derived from chunk_size)
            # Note: chunk_size counts rows for COPY; for INSERTs use it as statement batch size
            total_rows = execute_insert_batches(dsn, inserts_iter, max(100, args.chunk_size // 1000), env)

        print(f"Completed. Total rows loaded: {total_rows}")


if __name__ == "__main__":
    main()