---
description: Stop idle slots (staging + inactive production slot)
---

# Cleanup Idle Slots

Stop staging and inactive production slot to free up server resources.

## Behavior

1) **Identify slots to stop**:
   - SSH to server
   - Read active production slot: `cat /opt/tvunah/.active_slot`
   - Determine idle slots:
     - Staging (always stopped during cleanup)
     - Inactive production slot (blue if green active, or vice versa)

2) **Display cleanup plan**:
   ```
   === Cleanup Plan ===
   Active production: {active_slot} (will keep running)

   Will stop:
   - Staging slot (ports 3020/4020)
   - {inactive_slot} slot (ports {ports})

   This will free up server resources but you won't be able to:
   - Test staging until next /dpl-stage
   - Instant rollback to {inactive_slot}

   Continue? (y/n):
   ```

   If user says no: exit without changes
   If user says yes: continue

3) **Stop staging slot**:
   - Run: `docker compose -f docker-compose.staging.yml down`
   - Verify containers stopped
   - Report status

4) **Stop inactive production slot**:
   - Run: `docker compose -f docker-compose.{inactive_slot}.yml down`
   - Verify containers stopped
   - Report status

5) **Summary**:
   ```
   === Cleanup Complete ===

   Stopped:
   ✓ Staging slot
   ✓ {inactive_slot} slot

   Running:
   ✓ {active_slot} slot (serving production)
   ✓ Redis (shared)

   To deploy again: /dpl-stage
   ```

6) **Audio notification** (optional):
   - If `--say` flag is set: use `/say` to speak brief completion message
   - Message: "Cleanup complete" (max 10 words)
   - If `--say` NOT set (default): skip this step silently

## Arguments (from {{ARGS}})

- `--yes` or `-y`: Skip confirmation prompt (auto-confirm)
- `--staging-only`: Only stop staging, keep inactive production slot
- `--prod-only`: Only stop inactive production slot, keep staging
- `--say`: Speak audio notification when cleanup completes. Default: Don't speak

## Notes

- Always preserves active production slot (never stops it)
- Preserves Redis container (shared across all slots)
- After cleanup, use `/dpl-stage` to deploy again
- Inactive slot provides instant rollback capability - cleanup only when confident
