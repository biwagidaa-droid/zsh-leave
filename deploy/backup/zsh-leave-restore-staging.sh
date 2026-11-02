#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

fail() {
    printf 'zsh-leave-restore-staging: %s\n' "$*" >&2
    exit 1
}

[[ "$#" == "1" ]] || fail "usage: zsh-leave-restore-staging.sh SNAPSHOT_DIRECTORY"
[[ "${ZSH_RESTORE_ISOLATED:-}" == "YES" ]] || fail "set ZSH_RESTORE_ISOLATED=YES only after verifying the separate staging cluster and credentials."
[[ -n "${ZSH_RESTORE_DB_NAME:-}" && "$ZSH_RESTORE_DB_NAME" == zsh_restore_* ]] || fail "staging database name must start with zsh_restore_."
[[ -n "${ZSH_RESTORE_DB_HOST:-}" && -n "${ZSH_RESTORE_DB_USER:-}" && -n "${ZSH_RESTORE_DB_PASSWORD:-}" ]] || fail "staging database connection settings are incomplete."
[[ -n "${ZSH_RESTORE_ATTACHMENT_ROOT:-}" && "$ZSH_RESTORE_ATTACHMENT_ROOT" == /* ]] || fail "ZSH_RESTORE_ATTACHMENT_ROOT must be an absolute staging path."
[[ -n "${ZSH_RESTORE_SCRATCH:-}" && "$ZSH_RESTORE_SCRATCH" == /* ]] || fail "ZSH_RESTORE_SCRATCH must be an absolute encrypted scratch path."
[[ -n "${ZSH_BACKUP_AGE_IDENTITY_FILE:-}" && -r "$ZSH_BACKUP_AGE_IDENTITY_FILE" ]] || fail "age identity must be readable from the secret manager or protected staging path."

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$script_dir/../.." && pwd -P)"
backend_dir="$repo_root/backend"
snapshot_dir="$(realpath -e -- "$1")" || fail "snapshot directory does not exist."
[[ -f "$snapshot_dir/COMPLETE" ]] || fail "snapshot is missing its COMPLETE marker."
identity_file="$(realpath -e -- "$ZSH_BACKUP_AGE_IDENTITY_FILE")" || fail "age identity file does not exist."
case "$identity_file/" in
    "$repo_root/"*) fail "age identity must be outside the repository." ;;
esac
for tool in age date find pg_restore psql python3 realpath sha256sum tar; do
    command -v "$tool" >/dev/null 2>&1 || fail "required tool is unavailable: $tool"
done

cd -- "$snapshot_dir"
sha256sum --check SHA256SUMS

[[ ! -L "$ZSH_RESTORE_SCRATCH" ]] || fail "restore scratch must not be a symlink."
scratch_root="$(realpath -m -- "$ZSH_RESTORE_SCRATCH")"
case "$scratch_root/" in
    "$repo_root/"*) fail "restore scratch must be outside the repository." ;;
    "$snapshot_dir/"*) fail "restore scratch must be outside the backup snapshot." ;;
esac
case "$snapshot_dir/" in
    "$scratch_root/"*) fail "backup snapshot must be outside restore scratch." ;;
esac

[[ ! -L "$ZSH_RESTORE_ATTACHMENT_ROOT" ]] || fail "staging attachment root must not be a symlink."
attachment_root="$(realpath -m -- "$ZSH_RESTORE_ATTACHMENT_ROOT")"
case "$attachment_root/" in
    "$repo_root/"*) fail "staging attachment root must be outside the repository." ;;
    "$scratch_root/"*) fail "staging attachment root must be outside restore scratch." ;;
esac
case "$scratch_root/" in
    "$attachment_root/"*) fail "restore scratch must be outside staging attachment storage." ;;
esac
case "$attachment_root/" in
    "$snapshot_dir/"*) fail "staging attachment root must be outside the backup snapshot." ;;
esac
case "$snapshot_dir/" in
    "$attachment_root/"*) fail "backup snapshot must be outside staging attachment storage." ;;
esac
case "$identity_file/" in
    "$scratch_root/"*|"$attachment_root/"*|"$snapshot_dir/"*) fail "age identity must be outside restore data paths." ;;
esac

if [[ -n "${ZSH_ATTACHMENT_ROOT:-}" ]]; then
    configured_attachment_root="$(realpath -m -- "$ZSH_ATTACHMENT_ROOT")"
    [[ "$configured_attachment_root" != "$attachment_root" ]] || fail "staging attachment root matches ZSH_ATTACHMENT_ROOT; refusing to continue."
fi

mkdir -p -- "$scratch_root" "$attachment_root"
chmod 700 -- "$scratch_root" "$attachment_root"
[[ -z "$(find "$attachment_root" -mindepth 1 -maxdepth 1 -print -quit)" ]] || fail "staging attachment root must be empty."

work_dir="$(mktemp -d "$scratch_root/zsh-leave-restore.XXXXXX")"
chmod 700 -- "$work_dir"
trap 'rm -rf -- "$work_dir"' EXIT

age --decrypt --identity "$identity_file" \
    "$snapshot_dir/inventory.json.age" > "$work_dir/inventory.json"
source_db_name="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["database_identity"]["name"])' "$work_dir/inventory.json")"
source_db_host="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["database_identity"]["host"])' "$work_dir/inventory.json")"
source_db_port="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["database_identity"]["port"])' "$work_dir/inventory.json")"
app_version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["application_version"])' "$work_dir/inventory.json")"
[[ -n "$source_db_name" && -n "$source_db_host" && -n "$source_db_port" ]] || fail "source database identity is incomplete in the inventory."
[[ "$source_db_name" != "$ZSH_RESTORE_DB_NAME" ]] || fail "target database name matches the backup source."
[[ "$source_db_host" != "$ZSH_RESTORE_DB_HOST" || "$source_db_port" != "${ZSH_RESTORE_DB_PORT:-5432}" ]] || fail "target database host and port match the backup source."
[[ -n "$app_version" && "$app_version" != "unknown" ]] || fail "backup inventory has no application version."
running_app_version="${ZSH_APP_VERSION:-}"
[[ -n "$running_app_version" ]] || fail "ZSH_APP_VERSION must identify the deployed release or commit."
[[ "$running_app_version" == "$app_version" ]] || fail "checked-out application version does not match the backup inventory."

export PGPASSWORD="$ZSH_RESTORE_DB_PASSWORD"
table_count="$(psql -X -A -t -v ON_ERROR_STOP=1 \
    --host="$ZSH_RESTORE_DB_HOST" \
    --port="${ZSH_RESTORE_DB_PORT:-5432}" \
    --username="$ZSH_RESTORE_DB_USER" \
    --dbname="$ZSH_RESTORE_DB_NAME" \
    --command="SELECT (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')) + (SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname NOT IN ('pg_catalog', 'information_schema', 'public') AND nspname NOT LIKE 'pg_%')")"
[[ "$table_count" == "0" ]] || fail "staging database is not empty; no restore was attempted."

age --decrypt --identity "$identity_file" \
    "$snapshot_dir/database.dump.age" > "$work_dir/database.dump"
pg_restore --list "$work_dir/database.dump" > "$work_dir/database.toc"
age --decrypt --identity "$identity_file" \
    "$snapshot_dir/attachments.tar.gz.age" > "$work_dir/attachments.tar.gz"
tar -tzf "$work_dir/attachments.tar.gz" > "$work_dir/attachments.list"

pg_restore --exit-on-error --no-owner --no-acl \
    --host="$ZSH_RESTORE_DB_HOST" \
    --port="${ZSH_RESTORE_DB_PORT:-5432}" \
    --username="$ZSH_RESTORE_DB_USER" \
    --dbname="$ZSH_RESTORE_DB_NAME" \
    "$work_dir/database.dump"
tar --no-same-owner -xzf "$work_dir/attachments.tar.gz" -C "$attachment_root"

export DJANGO_SETTINGS_MODULE=config.settings_prod
export ZSH_DB_HOST="$ZSH_RESTORE_DB_HOST"
export ZSH_DB_PORT="${ZSH_RESTORE_DB_PORT:-5432}"
export ZSH_DB_NAME="$ZSH_RESTORE_DB_NAME"
export ZSH_DB_USER="$ZSH_RESTORE_DB_USER"
export ZSH_DB_PASSWORD="$ZSH_RESTORE_DB_PASSWORD"
export ZSH_ATTACHMENT_ROOT="$attachment_root"
export ZSH_APP_VERSION="$running_app_version"
cd -- "$backend_dir"
python3 manage.py migrate --noinput
python3 manage.py migrate --check
python3 manage.py check
python3 manage.py verify_backup --compare "$work_dir/inventory.json"
printf 'Staging restore checks passed for database %s on %s:%s.\n' \
    "$ZSH_RESTORE_DB_NAME" "$ZSH_RESTORE_DB_HOST" "${ZSH_RESTORE_DB_PORT:-5432}"