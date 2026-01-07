---
description: Build and deploy to staging for testing before production
---

# Deploy to Staging

Build and deploy application to staging environment for testing before shipping to production.

## Behavior

1) **Code preparation**:
   - If `--merge-main` flag set: forward merge `origin/main` into `origin/staging`
   - Otherwise: use current `origin/staging`
   - Checkout staging branch locally
   - Verify no direct commits in staging (only merge commits allowed):
     - Check: `git log staging --not main --oneline --no-merges`
     - If direct commits found: WARN user and offer options:
       - A) Continue anyway (deploy with direct commits)
       - B) Abort and review commits first
     - If user chooses abort: exit without changes

2) **Local testing** (ALWAYS runs, track time):
   - Run `./scripts/run_tests.sh` (backend + frontend tests)
   - If tests FAIL: Explain which tests failed, STOP, do NOT proceed
   - If tests PASS: continue to staging deployment

3) **Server preparation**:
   - SSH to `boris@go.tvunah.ai`
   - Pull latest `origin/staging`
   - Extract git hash (7 chars) for version

4) **Frontend local build** (track time):
   - Build frontend locally: `./scripts/docker_build.sh --version={hash} --services=frontend`
   - This creates `frontend-build-{hash}.tar.gz` locally
   - Transfer artifacts: `./scripts/transfer_frontend_build.sh --version={hash}`

5) **Server-side build** (track time):
   - SSH to `boris@go.tvunah.ai`
   - Update `GIT_HASH` in `env/staging.env`
   - Build backend: `./scripts/docker_build.sh --version={hash} --services=backend`
   - Build frontend image: `./scripts/docker_build.sh --version={hash} --services=frontend`
   - Verify images built successfully

6) **Validate environment configuration**:
   - Run `./scripts/validate_env.sh env/staging.env`
   - Check that all required secrets are configured (not placeholders)
   - If validation fails: STOP and show clear error with instructions
   - Required: OPENAI_API_KEY, OPENAI_PROJECT_ID, SESSION_SECRET_KEY, STAGING_DATABASE_URL
   - NEVER commit secrets to git (env files are gitignored)

7) **Deploy to staging** (track time):
   - Deploy: `./scripts/docker_deploy.sh --slot=staging --version={hash}`
   - Note: Migrations run automatically during deployment (Step 5 in docker_deploy.sh)
   - Monitor container startup

8) **Smoke tests**:
   - Test frontend: `curl http://localhost:3020/` → HTTP 200
   - Test backend: `curl http://localhost:4020/health` → verify git_hash
   - If smoke tests FAIL: report error

9) **Always back-merge staging → main**:
   - After successful staging deployment, always back-merge changes to main
   - Checkout main: `git checkout main`
   - Pull latest: `git pull origin main`
   - Merge staging: `git merge staging --no-edit -m "chore: back-merge staging to main"`
   - If conflicts detected:
     - PAUSE, display conflict files
     - Offer options:
       - A) Manually resolve conflicts now (open editor)
       - B) Skip back-merge (user must do it manually later)
     - If user chooses skip: WARN that main is not synced
     - If user resolves: continue with resolved merge
   - Push to remote: `git push origin main`
   - This ensures staging fixes always sync back to development

10) **Identify changes since last staging**:
   - Get previous staging deployment hash from server:
     - SSH to `boris@go.tvunah.ai`
     - Extract previous `GIT_HASH` from staging slot before it was updated
     - Use git tag or docker label to find last staging version
   - Find closed issues between last staging and current:
     - Get commit range: `git log {prev_hash}..{current_hash} --oneline`
     - Extract issue numbers from commit messages (pattern: `#\d+`)
     - Fetch issue details: `gh issue view {number} --json state,title,labels`
     - Filter for closed issues only
   - Generate testing recommendations:
     - Group issues by type: feat, fix, refactor, test
     - For each closed issue, extract key testing area from title/labels
     - Prioritize features and fixes for manual testing
     - Generate 3-5 concrete testing suggestions

11) **Display staging info**:
   ```
   === Staging Deployment Complete ===
   Version: {hash}

   Timing:
   - Local tests:          X min
   - Frontend build:       X min (local)
   - Artifact transfer:    X sec
   - Backend build:        X min (server)
   - Frontend image:       X sec (server)
   - Deploy:               X min
   - Total:                X min

   Status: ✅ STAGED

   === Changes Since Last Staging ===
   Previous version: {prev_hash}

   Closed Issues (X):
   - #123 feat: Add user authentication → Test: login/logout flow
   - #456 fix: Fix calculation bug → Test: recalculate existing analyses
   - #789 feat: Export to PDF → Test: export large/small reports

   Key Testing Areas:
   1. {Area 1 from features} - {specific action to test}
   2. {Area 2 from fixes} - {specific action to test}
   3. {Area 3 from critical changes} - {specific action to test}

   To test staging from your laptop:

   1. Ensure tunnel is running:
      ./scripts/tunnels.sh status

      If staging-app tunnel is not running:
      ./scripts/tunnels.sh start staging-app

   2. Access staging app:
      http://localhost:13020

   3. View staging database (SQLTools):
      Connection: "Staging (go.tvunah.ai)" in VSCode SQLTools

   4. When done testing, promote to production:
      /dpl-ship

   Manual access (if needed):
      Frontend: ssh -L 8080:localhost:3020 boris@go.tvunah.ai → http://localhost:8080
      Backend:  ssh -L 8081:localhost:4020 boris@go.tvunah.ai → http://localhost:8081
      Database: ssh -L 5433:localhost:5432 boris@go.tvunah.ai → localhost:5433

   To view staging logs:
      ssh boris@go.tvunah.ai "cd /opt/tvunah && docker compose -f docker-compose.staging.yml logs -f"
   ```

12) **Audio notification** (optional):
    - If `--say` flag is set: use `/say` to speak brief completion message
    - Message: "Staging deployment complete" (max 10 words)
    - If `--say` NOT set (default): skip this step silently

## Arguments (from {{ARGS}})

- `--merge-main`: Forward merge origin/main into origin/staging before deployment. Default: Don't merge
- `--say`: Speak audio notification when deployment completes. Default: Don't speak

## Prerequisites

**IMPORTANT: Environment configuration must be set up on the server before first deployment**

On server (`boris@go.tvunah.ai`), ensure `/opt/tvunah/env/staging.env` has real values:

1. Copy example if needed:
   ```bash
   ssh boris@go.tvunah.ai
   cd /opt/tvunah
   cp env/staging.env.example env/staging.env
   ```

2. Edit with real secrets:
   ```bash
   nano env/staging.env
   ```

3. Required variables (replace ALL placeholders):
   - `OPENAI_API_KEY` - Valid OpenAI API key (test key recommended)
   - `OPENAI_PROJECT_ID` - OpenAI project ID
   - `SESSION_SECRET_KEY` - Random 32+ character string
   - `STAGING_DATABASE_URL` - PostgreSQL connection URL

4. **NEVER commit secrets to git** - env files are already gitignored

The deployment script will automatically validate the configuration and fail with clear errors if any placeholders remain.

## Notes

- Staging runs on ports 3020 (frontend) / 4020 (backend)
- Not accessible publicly - only via SSH tunnel
- Unified tunnel script manages all SSH tunnels: `./scripts/tunnels.sh`
  - Staging app tunnel: localhost:13020 → go.tvunah.ai:3020
  - Staging DB tunnel: localhost:15433 → go.tvunah.ai:5432 (tvunah_staging)
  - Auto-starts on VSCode workspace open
- Tests ALWAYS run - quality is 100% critical
- After successful staging, use `/dpl-ship` to promote to production
- Environment validation runs automatically on every deployment
