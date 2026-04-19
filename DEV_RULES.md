# DEV_RULES.md

## Mandatory development rules

1. Two-strike rule
- If the same error appears twice, stop patching immediately.
- Switch to audit, traceback collection, rollback, or baseline selection.
- No third patch on the same symptom is allowed without new evidence.

2. No blind patching
- Never patch code without first dumping the exact target block from the live file.
- Use `sed`, `grep -n`, or equivalent read-only inspection first.
- Patch only against the real current file contents.

3. Backups are untrusted by default
- A backup file is not assumed to be healthy.
- Every backup must be audited before reuse:
  - syntax check
  - key symbol presence
  - expected behavior markers
- Only audited backups may be used as rollback baselines.

4. One patch = one isolated change
- Each patch must change only one logical layer.
- Do not mix runtime, rendering, validation, fallback, navigation, or premium logic in one patch.
- If multiple layers are broken, fix them sequentially.

5. Traceback is the source of truth
- Root cause must be based on traceback, logs, or directly observed failure evidence.
- Do not infer root cause from intuition alone.
- If traceback contradicts assumptions, traceback wins.

## Required workflow

For every bugfix:
1. Reproduce the bug
2. Capture traceback or exact error
3. Dump the exact target code block
4. Define one isolated layer to change
5. Apply one patch only
6. Run syntax check
7. Restart only if syntax is green
8. Re-test the exact failing scenario

## Patch acceptance criteria

A patch is valid only if:
- the target block was inspected before patching
- the patch changes one isolated layer
- syntax check passes
- the original failing scenario was re-tested
- no previous mandatory rule was violated

## Invalid behavior

The following makes a solution invalid:
- repeating the same failed fix pattern
- patching without exact code dump
- trusting a backup without audit
- mixing multiple logical changes in one patch
- fixing by guess instead of traceback

## Operational preference

Default development mode:
- read-only audit first
- then minimal patch
- then syntax check
- then restart
- then focused smoke test
