---
description: Ship staged version to production
---

# Ship to Production

Promote the staged version to production with zero-downtime blue/green deployment.

## Behavior

1) **Pre-ship checks**:
   - SSH to server
   - Read staging version: `curl -s http://localhost:4020/health | jq -r .git_hash`
   - Read current active slot: `cat /opt/tvunah/.active_slot`
   - Read current production version: `curl -s https://go.tvunah.ai/health | jq -r .git_hash`
   - Determine target slot (opposite of active: blue active → ship to green, green active → ship to blue)

2) **User confirmation**:
   Display summary and prompt:
   ```
   === Ready to Ship ===
   Staging version:    {staging_hash}
   Current production: {prod_hash} on {active_slot}
   Target slot:        {target_slot}

   This will:
   - Forward merge staging → prod
   - Deploy {staging_hash} to {target_slot} slot
   - Switch production traffic to {target_slot}
   - Always back-merge prod → main (sync development)
   - Keep {active_slot} running for instant rollback

   Ship to production? (y/n):
   ```

   If user says no: exit without changes
   If user says yes: continue

3) **Forward merge staging → prod**:
   - Checkout prod: `git checkout prod`
   - Pull latest: `git pull origin prod`
   - Merge staging: `git merge staging --no-edit -m "chore: forward merge staging to prod"`
   - Verify no direct commits in prod (only merge commits allowed):
     - Check: `git log prod --not staging --oneline --no-merges`
     - If direct commits found: WARN user (should only happen with hotfixes)
   - Push to remote: `git push origin prod`

4) **Deploy to target slot** (track time):
   - Update `GIT_HASH` in `env/{target_slot}.env`
   - Deploy: `./scripts/docker_deploy.sh --slot={target_slot} --version={staging_hash}`
   - Note: Images already built during staging, just deploying containers
   - Note: Migrations run automatically during deployment (Step 5 in docker_deploy.sh)
   - Monitor container startup

5) **Smoke tests on target slot**:
   - Test frontend: `curl http://localhost:{target_port}/` → HTTP 200
   - Test backend: `curl http://localhost:{target_port+1000}/health` → verify git_hash matches staging
   - If smoke tests FAIL: STOP, do not switch traffic

6) **Traffic switch** (track time):
   - Update nginx config: `/etc/nginx/conf.d/tvunah_active.conf`
   - Update `.active_slot` file
   - Reload nginx: `sudo systemctl reload nginx`
   - Verify: `curl -s https://go.tvunah.ai/health` → check git_hash and slot_name

7) **Always back-merge prod → main**:
   - After successful production deployment, always back-merge to main
   - Checkout main: `git checkout main`
   - Pull latest: `git pull origin main`
   - Merge prod: `git merge prod --no-edit -m "chore: back-merge prod to main"`
   - If conflicts detected:
     - PAUSE, display conflict files
     - Offer options:
       - A) Manually resolve conflicts now (open editor)
       - B) Skip back-merge (user must do it manually later)
     - If user chooses skip: WARN that main is not synced
     - If user resolves: continue with resolved merge
   - Push to remote: `git push origin main`
   - This ensures production changes always sync back to development
   - Note: This creates fast-forward merge in normal flow (simplicity over conditional logic)

8) **Post-ship summary**:
   ```
   === Ship Complete ===
   Previous: {old_slot} ({old_hash})
   Current:  {new_slot} ({new_hash})

   Timing:
   - Deploy:         X min
   - Traffic switch: X sec
   - Total:          X min

   Status: ✅ SHIPPED
   URL: https://go.tvunah.ai

   Note: {old_slot} slot is still running for instant rollback if needed.
   To clean up idle slots, run: /dpl-cleanup
   To roll back, run /dpl-rollback
   ```

9) **Audio notification** (optional):
   - If `--say` flag is set: use `/say` to speak brief completion message
   - Message: "Production deployment complete" (max 10 words)
   - If `--say` NOT set (default): skip this step silently

## Arguments (from {{ARGS}})

- `--yes` or `-y`: Skip confirmation prompt (auto-confirm)
- `--force`: Force traffic switch even if health checks fail (DANGEROUS)
- `--say`: Speak audio notification when deployment completes. Default: Don't speak

## Error Handling

- If staging slot not running: error, cannot ship
- If deployment fails: STOP, old slot keeps serving
- If smoke tests fail: STOP, do not switch traffic
- If anything fails: production unaffected (zero-risk)

## Notes

- Reuses Docker images from staging (no rebuild)
- Previous production slot stays running for safety
- Zero-downtime deployment via blue/green switching
- Use `/dpl-cleanup` after confirming new version is stable
