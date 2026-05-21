# Cleanup architecture status — 2026-05-21

## Current HEAD

1775294

## Completed layers

- Cleanup inventory tool
- Cleanup classifier tool
- Runtime garbage cleanup tool
- Backup retention audit tool
- Diagnostics preservation audit tool
- Safety snapshot tool
- Final sanitation audit tool
- Controlled runtime garbage destructive cleanup

## Runtime cleanup result

Runtime garbage destructive cleanup was executed only for approved runtime garbage:

- `.pyc`
- `.pyo`
- `bot.log`
- empty `.db` / `.sqlite` files inside `data/`

The first apply stopped on root-owned `__pycache__` files with `Permission denied`.

The cause was audited and confirmed:

- remaining files were root-owned runtime garbage
- no `venv/` paths were present
- no protected diagnostics were touched
- no historical backups were touched

Remaining runtime garbage was removed with `sudo rm` using the dry-run candidate list.

Final runtime dry-run result: empty.

## Current blocked destructive areas

Backup destructive cleanup remains blocked.

Reason:

- no approved deletion set exists yet
- all backup-like files are classified as protected or review-required

Diagnostics destructive cleanup remains blocked.

Reason:

- no approved deletion set exists yet
- all diagnostics directories are classified as protected or review-required

## Safety status

- `venv/` excluded
- tracked-source snapshot tool available
- final sanitation audit available
- compile sanity green after cleanup
- service active after cleanup
- worktree clean after cleanup

## Next allowed layers

1. Build explicit approved deletion set for historical backups, if needed.
2. Build explicit approved deletion set for diagnostics, if needed.
3. Start legacy naming decontamination audit:
   - `workinportugal`
   - `Work in Portugal`
   - `workinportugal_bot`
4. Start restaurants/template decontamination audit:
   - separate real restaurants section from reusable catalog schema flow
