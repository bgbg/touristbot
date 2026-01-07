---
description: Emergency hotfix with automated merge cascade
---

# Hotfix Deployment with Merge Cascade

Deploy emergency production fixes with automated back-merge cascade to prevent environment desync.

## Behavior

### Phase 1: Pre-flight Checks

1) **Verify hotfix is merged to prod**:
   - SSH to server
   - Check current branch: `git branch --show-current`
   - If not on `prod` branch: error, must merge hotfix to prod first
   - Verify commit: `git log -1 --oneline`
   - Read current production version: `curl -s https://go.tvunah.ai/health | jq -r .git_hash`

2) **Check for WIP in staging**:
   - Check if staging branch has uncommitted changes: `git -C /opt/tvunah status --short`
   - Check if staging has commits not in prod: `git log prod..staging --oneline`
   - If WIP found: WARN user and offer options:
     - A) Continue anyway (WIP will be merged to main, may cause conflicts)
     - B) Abort and manually handle staging WIP first
     - C) Dry-run mode to preview merge cascade
   - If user chooses abort: exit without changes

3) **User confirmation**:
   Display summary and prompt:
   ```
   === Hotfix Deployment ===
   Current production: {prod_hash}
   Hotfix to deploy:   {hotfix_hash}

   This will:
   1. Deploy {hotfix_hash} to production (standard deployment)
   2. After deployment: Automated merge cascade
      - prod → staging (sync staging environment)
      - staging → main (sync development)

   Staging WIP status: {wip_status}

   Deploy hotfix and run merge cascade? (y/n):
   ```

   If user says no: exit without changes
   If user says yes: continue

### Phase 2: Deploy Hotfix

4) **Deploy to production** (standard procedure):
   - Use existing deployment flow: `/dpl-stage` then `/dpl-ship`
   - Or if deploying directly to prod: follow deployment_runbook.md steps
   - This phase is identical to normal production deployment
   - Wait for deployment to complete and verify production is healthy

### Phase 3: Automated Merge Cascade

5) **Dry-run mode** (if `--dry-run` flag set):
   - Preview all merges without executing: `git merge --no-commit --no-ff <branch>`
   - Show what would be merged to staging and main
   - Display potential conflicts
   - Exit without making changes
   - User can then decide to proceed with real merge

6) **Back-merge prod → staging**:
   - Checkout staging: `git checkout staging`
   - Pull latest: `git pull origin staging`
   - Attempt merge: `git merge prod --no-edit -m "chore: back-merge prod hotfix to staging"`
   - If conflicts detected:
     - PAUSE cascade, display conflict files
     - Offer options:
       - A) Manually resolve conflicts now (open editor)
       - B) Abort cascade and resolve manually later
       - C) Skip staging merge, continue to main (RISKY)
     - If user chooses abort: rollback merge, exit
     - If user resolves: continue with resolved merge
   - Push to remote: `git push origin staging`

7) **Back-merge staging → main**:
   - Checkout main: `git checkout main`
   - Pull latest: `git pull origin main`
   - Attempt merge: `git merge staging --no-edit -m "chore: back-merge staging (includes hotfix) to main"`
   - If conflicts detected:
     - PAUSE cascade, display conflict files
     - Offer options:
       - A) Manually resolve conflicts now (open editor)
       - B) Abort cascade, leave main unsynced (user must fix later)
     - If user chooses abort: rollback merge, exit with warning
     - If user resolves: continue with resolved merge
   - Push to remote: `git push origin main`

8) **Cascade complete summary**:
   ```
   === Hotfix Cascade Complete ===
   Hotfix:  {hotfix_hash}
   Merges:  prod → staging → main

   Status: ✅ ALL ENVIRONMENTS SYNCED

   Next steps:
   - Verify staging: curl http://localhost:3020/health
   - Local development: git pull origin main

   Note: If conflicts occurred, they were resolved during cascade.
   ```

9) **Rollback procedure** (if cascade fails mid-way):
   - If staging merge succeeded but main merge failed:
     - staging is ahead of prod (safe, can continue later)
     - main is behind staging (WARN user to fix manually)
     - Suggest: manually merge staging to main when ready
   - If staging merge failed:
     - prod deployed successfully (production safe)
     - staging not synced (WARN user to merge manually)
     - main not synced (WARN user to merge manually)
     - Suggest: manually run cascade when ready

## Arguments (from {{ARGS}})

- `--dry-run`: Preview merge cascade without executing (shows potential conflicts)
- `--yes` or `-y`: Skip confirmation prompt (auto-confirm deployment and cascade)
- `--skip-staging`: Skip staging merge, only merge prod → main (RISKY, use only if staging broken)
- `--no-push`: Perform merges locally but don't push to remote (for testing)

## Error Handling

- If not on prod branch: error, cannot deploy hotfix
- If production deployment fails: STOP, no merge cascade
- If staging merge conflicts: PAUSE, offer resolution options
- If main merge conflicts: PAUSE, offer resolution options
- If cascade aborted: production remains healthy, staging/main need manual sync
- If network error during push: local merges succeeded, manual push required

## Notes

- Hotfixes MUST be merged to `prod` branch before running this command
- Automated cascade eliminates manual merge errors and environment desync
- WIP detection prevents accidental merge of incomplete staging work
- Dry-run mode allows safe preview of merge cascade
- Conflict resolution is interactive and safe (pause, resolve, continue)
- If cascade fails, production is never affected (zero-risk)
- Use `--skip-staging` only in emergencies (e.g., staging branch corrupted)

## Workflow Pattern

**Recommended hotfix workflow:**
```bash
# 1. Create hotfix branch from prod
git checkout -b hotfix/critical-fix prod

# 2. Make fixes, test locally
# ... make changes ...
git commit -m "fix: critical security issue"

# 3. Merge to prod
git checkout prod
git merge hotfix/critical-fix
git push origin prod

# 4. Deploy hotfix with automated cascade
/dpl-hotfix

# This handles:
# - Deploy to production
# - Back-merge prod → staging
# - Back-merge staging → main
# - All environments synced automatically
```

## Advanced Usage

**Dry-run before deployment:**
```bash
/dpl-hotfix --dry-run
# Reviews merge cascade, shows potential conflicts
# If conflicts found: resolve locally first, then deploy
```

**Skip confirmation (CI/CD automation):**
```bash
/dpl-hotfix --yes
# Auto-confirms deployment and cascade
# Use only in automated environments
```

**Handle staging WIP manually:**
```bash
# If staging has WIP and you want to preserve it:
git checkout staging
git stash push -m "WIP before hotfix cascade"
/dpl-hotfix
git stash pop  # Restore WIP after cascade
```
