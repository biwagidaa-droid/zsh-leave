#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

fail() {
    printf 'zsh-leave-backup: %s\n' "$*" >&2
    exit 1
}

[[ "${ZSH_BACKUP_QUIESCED:-}" == "1" ]] || fail "set ZSH_BACKUP_QUIESCED=1 only after web writers and scheduled jobs are stopped."
[[ "${DJANGO_SETTINGS_MODULE:-}" == "config.settings_prod" ]] || fail "DJANGO_SETTINGS_MODULE must be config.settings_prod."
[[ -n "${ZSH_DB_NAME:-}" && -n "${ZSH_DB_USER:-}" && -n "${ZSH_DB_PASSWORD:-}" ]] || fail "production database settings are incomplete."
[[ -n "${ZSH_ATTACHMENT_ROOT:-}" ]] || fail "ZSH_ATTACHMENT_ROOT is required."
[[ -n "${ZSH_BACKUP_DIR:-}" ]] || fail "ZSH_BACKUP_DIR must name a private backup destination."
[[ -n "${ZSH_BACKUP_AGE_RECIPIENT:-}" ]] || fail "ZSH_BACKUP_AGE_RECIPIENT must be supplied by deployment configuration."

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$script_dir/../.." && pwd -P)"
backend_dir="$repo_root/backend"
attachment_root="$(realpath -e -- "$ZSH_ATTACHMENT_ROOT")" || fail "attachment root does not exist."
[[ -d "$attachment_root" && ! -L "$ZSH_ATTACHMENT_ROOT" ]] || fail "attachment root must be a real directory, not a symlink."
case "$attachment_root/" in
    "$repo_root/"*) fail "attachment root must not be inside the repository." ;;
esac

mkdir -p -- "$ZSH_BACKUP_DIR"
[[ ! -L "$ZSH_BACKUP_DIR" ]] || fail "backup destination must not be a symlink."
chmod 700 -- "$ZSH_BACKUP_DIR"
backup_dir="$(realpath -e -- "$ZSH_BACKUP_DIR")"
case "$backup_dir/" in
    "$repo_root/"*) fail "backup destination must be outside the repository." ;;
    "$attachment_root/"*) fail "backup destination must be outside the attachment root." ;;
esac

for tool in age date flock pg_dump python3 realpath sha256sum tar; do
    command -v "$tool" >/dev/null 2>&1 || fail "required tool is unavailable: $tool"
done

app_version="${ZSH_APP_VERSION:-}"
[[ -n "$app_version" ]] || fail "ZSH_APP_VERSION must identify the deployed release or commit."

exec 9>"$backup_dir/.zsh-leave-backup.lock"
flock -n 9 || fail "another backup is already running."

snapshot_id="$(date -u +%Y%m%dT%H%M%SZ)"
stage_dir="$(mktemp -d "$backup_dir/.zsh-leave-${snapshot_id}.XXXXXX")"
chmod 700 -- "$stage_dir"
trap 'rm -rf -- "$stage_dir"' EXIT

db_password="$ZSH_DB_PASSWORD"
export -n ZSH_DB_PASSWORD
PGPASSWORD="$db_password" pg_dump \
    --format=custom \
    --no-owner \
    --no-acl \
    --host="${ZSH_DB_HOST:-db}" \
    --port="${ZSH_DB_PORT:-5432}" \
    --username="$ZSH_DB_USER" \
    "$ZSH_DB_NAME" \
    | age --encrypt --recipient "$ZSH_BACKUP_AGE_RECIPIENT" \
        > "$stage_dir/database.dump.age"

tar -C "$attachment_root" -czf - . \
    | age --encrypt --recipient "$ZSH_BACKUP_AGE_RECIPIENT" \
        > "$stage_dir/attachments.tar.gz.age"

cd -- "$backend_dir"
ZSH_DB_PASSWORD="$db_password" ZSH_APP_VERSION="$app_version" python3 manage.py verify_backup \
    | age --encrypt --recipient "$ZSH_BACKUP_AGE_RECIPIENT" \
        > "$stage_dir/inventory.json.age"

cd -- "$stage_dir"
sha256sum database.dump.age attachments.tar.gz.age inventory.json.age > SHA256SUMS
printf 'snapshot_id=%s\ncreated_at_utc=%s\n' "$snapshot_id" "$(date -u +%FT%TZ)" > COMPLETE

final_dir="$backup_dir/$snapshot_id"
[[ ! -e "$final_dir" ]] || fail "snapshot destination already exists: $final_dir"
mv -- "$stage_dir" "$final_dir"
trap - EXIT
printf 'Encrypted snapshot created: %s\n' "$final_dir"