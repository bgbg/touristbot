---
description: Instantly rollback to previous production version
---

# Rollback to Previous Version

Instantly switch production traffic back to the previous slot (instant rollback).

## Behavior

1) **Pre-rollback checks**:
   - SSH to server
   - Read current active slot: `cat /opt/tvunah/.active_slot`
   - Read current production version: `curl -s https://go.tvunah.ai/health | jq -r .git_hash`
   - Determine rollback slot (opposite of active: blue active → rollback to green, green active → rollback to blue)
   - Check if rollback slot is running: `docker ps | grep tvunah-{rollback_slot}`
   - Read rollback slot version: `curl -s http://localhost:{rollback_port+1000}/health | jq -r .git_hash`

2) **User confirmation**:
   Display summary and prompt:
   ```
   === Ready to Rollback ===
   Current production: {current_hash} on {active_slot}
   Rollback to:        {rollback_hash} on {rollback_slot}

   This will:
   - Switch production traffic to {rollback_slot}
   - Revert to version {rollback_hash}
   - Keep {active_slot} running

   WARNING: This immediately affects production users!

   Rollback to {rollback_slot}? (y/n):
   ```

   If user says no: exit without changes
   If user says yes: continue

3) **Verify rollback slot health**:
   - Check containers running: `docker ps --filter name=tvunah-{rollback_slot}`
   - Test frontend: `curl http://localhost:{rollback_port}/` → HTTP 200
   - Test backend: `curl http://localhost:{rollback_port+1000}/health` → verify healthy
   - If rollback slot NOT running or unhealthy: ERROR, cannot rollback

4) **Traffic switch** (track time):
   - Update nginx config: `/etc/nginx/conf.d/tvunah_active.conf`
   - Point to rollback slot ports
   - Update `.active_slot` file
   - Reload nginx: `sudo systemctl reload nginx`
   - Verify: `curl -s https://go.tvunah.ai/health` → check git_hash and slot_name

5) **Post-rollback summary**:
   ```
   === Rollback Complete ===
   Previous: {old_slot} ({old_hash})
   Current:  {rollback_slot} ({rollback_hash})

   Timing:
   - Traffic switch: X sec

   Status: ✅ ROLLED BACK
   URL: https://go.tvunah.ai

   Note: Rollback was instant (no rebuild needed).
   Both slots are still running.

   Next steps:
   - Investigate why {old_hash} needed rollback
   - Fix issues before deploying again
   - Use /dpl-cleanup when ready to free resources
   ```

6) **Audio notification** (optional):
   - If `--say` flag is set: use `/say` to speak brief completion message
   - Message: "Rollback complete" (max 10 words)
   - If `--say` NOT set (default): skip this step silently

## Arguments (from {{ARGS}})

- `--yes` or `-y`: Skip confirmation prompt (auto-confirm)
- `--say`: Speak audio notification when rollback completes. Default: Don't speak

## Error Handling

- If rollback slot not running: ERROR, cannot rollback
  - Message: "Cannot rollback - {rollback_slot} slot is not running. Deploy a working version first."
- If rollback slot unhealthy: ERROR, cannot rollback
  - Message: "Cannot rollback - {rollback_slot} slot is unhealthy. Check logs: docker compose -f docker-compose.{rollback_slot}.yml logs"
- Rollback is instant if previous slot is running and healthy

## Notes

- **Instant rollback**: No rebuild, just traffic switch (~5 seconds)
- **Requires previous slot running**: Rollback only works if inactive slot is still up
- **Zero-downtime**: Traffic switch via nginx reload
- **Safe operation**: Verifies rollback target is healthy before switching
- After `/dpl-cleanup`, rollback is not available (inactive slot stopped)

## Example Scenarios

**Scenario 1: Just shipped, found bug**
```
/dpl-ship              # Shipped v2 to blue
(discover bug in v2)
/dpl-rollback          # Instant rollback to green (v1)
```

**Scenario 2: After cleanup**
```
/dpl-ship              # Shipped v2 to blue
/dpl-cleanup           # Stopped green slot
(discover bug in v2)
/dpl-rollback          # ERROR: green not running
                       # Must deploy v1 to green first
```

**Best practice**: Keep inactive slot running until confident new version is stable.
