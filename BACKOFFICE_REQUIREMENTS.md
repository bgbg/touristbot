# Backoffice UI - Requirements

## Architecture

- **Monorepo** — backoffice lives in this repo under `backoffice/` (with `backoffice/frontend/` for Next.js and `backoffice/bff/` for the Python/FastAPI BFF)
- **Frontend**: Next.js with Material UI (MUI) component library
- **Database + Auth**: Supabase (PostgreSQL + Supabase Auth with magic link / passwordless)
- **BFF ↔ Bot Backend**: BFF communicates with the existing FastAPI bot backend via direct HTTP API calls (using API keys)
- **Deployment target**: To be decided later (build output kept deployment-agnostic)
- **Existing Streamlit apps** (admin_ui/, gemini/main_qa.py) coexist during transition

## Multi-Tenancy

- **Hierarchy**: Organization → Area → Site
- **GCS storage**: Shared bucket with org-prefixed paths (e.g., `gs://bucket/{org_id}/conversations/...`)
- **WhatsApp**: One phone number per organization
- **User ownership**: Users belong to exactly one org and can see/manage everything within that org (no per-user area ownership)

## Roles

### Global Admin
- Create, edit, delete **organizations**
- **Invite** users (triggers magic link email)
- **Disable/enable** user accounts
- **Remove** users from orgs
- **Impersonate** users (view UI from their perspective, for support/debugging)

### User (Org Member)
- Manage everything within their assigned org:
  - Areas and sites (full CRUD)
  - Documents (upload, view, delete)
  - Prompts (full template editing)
  - Customers / WhatsApp allowlist
  - View chat history and dashboard

## Authentication

- **Provider**: Supabase Auth
- **Method**: Magic link (passwordless) — login via email link, no passwords
- **Admin invites** new users by email, which triggers a magic link
- No password reset flow needed (passwordless by design)

## Areas & Sites

- **Full CRUD from UI**: Users can create new areas and sites from scratch (not just manage pre-existing ones)
- **Prompt editing**: Full template editing with a closed set of variables
  - Users see and edit the entire prompt text with `{{variable}}` placeholders
  - Variable list is fixed — adding new variables is not supported
  - Proper instructions/documentation for available variables must be presented to users

## Document Management

### Supported File Types
- DOCX (Microsoft Word)
- PDF
- TXT (plain text)
- Excel (.xlsx, .xls)
- CSV (comma-separated values)

### Manual Upload
- Upload, view, and delete documents through the UI
- Disabled when Google Drive is connected to the site

### Google Drive Integration
- **Scope**: Per-site (each site can have its own Drive folder)
- **Folder selection**: User selects a specific Google Drive folder
- **Sync mode**: Automatic periodic poll (~15 minutes)
- **Deletion behavior**: Files deleted in Google Drive are also deleted from the system
- **Override behavior**: When Drive is connected, manual uploads are disabled
- **UI when connected**: Read-only document list showing synced files (name, size, last sync status). Clear indicator that Drive is the source of truth

## Customer Management (WhatsApp Allowlist)

- **Access control scope**: Per-area
- **Modes**:
  - **Open**: Everyone can chat with the bot (no restrictions)
  - **Allowlist**: Only listed phone numbers can interact

### Phone Number Operations
- Add / delete individual numbers
- Optional **name** field per phone number
- **Bulk add/delete** via:
  - Paste text block (one number per line or comma-separated)
  - Upload CSV file
  - Upload Excel file
- All bulk formats support optional name column

## Chat History Dashboard

- **Access scope**: Org-wide (all areas and sites within the org)
- **Permissions**: View-only (no delete capability)
- **Features**:
  - Browse conversation list
  - Search and filter by date, area, site
  - Read individual conversations (full message thread)
  - **Basic metrics**:
    - Total conversations count
    - Average response time
    - Conversations per day chart
    - Top areas/sites by conversation volume

## Internationalization (i18n)

- **Supported languages**: English and Hebrew
- **RTL support**: Hebrew is right-to-left — layout, controls, and text direction must adapt accordingly
- **Language switching**: User toggle in the UI (e.g., header dropdown)
- **Preference persistence**: Language preference saved to user profile

## Phase 2 (Deferred)

These features are explicitly deferred and should NOT be built in phase 1:

1. **Chat preview widget** — Built-in chat widget for testing bot configuration live within the backoffice
2. **WhatsApp configuration UI** — Self-service setup of WhatsApp Business API credentials (phone number ID, access token, webhook URL) per org
3. **Notifications system** — In-app and/or email alerts for sync failures, new customers, bot errors, etc.

## Technical Decisions Summary

| Decision | Choice |
|----------|--------|
| Frontend framework | Next.js |
| UI component library | Material UI (MUI) |
| BFF backend | Python / FastAPI (separate from bot backend) |
| Database | Supabase (PostgreSQL) |
| Authentication | Supabase Auth (magic link / passwordless) |
| Repository | Monorepo (`backoffice/frontend/` + `backoffice/bff/`) |
| GCS strategy | Shared bucket, org-prefixed paths |
| Deployment | Decide later |
| Legacy UIs | Coexist during transition |
