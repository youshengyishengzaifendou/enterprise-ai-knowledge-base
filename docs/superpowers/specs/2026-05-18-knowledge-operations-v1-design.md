# Knowledge Operations V1 Design

## Commercial Target

Private-deployment customer-support knowledge assistant for small and midsize support teams.

## Product Boundary

This version improves knowledge operations around the existing assistant. It does not add live chat, ticketing, SLA workflows, SaaS multi-tenancy, or automatic replies to customers.

## Recommended Technical Priority

Create a safe upload-to-answer loop:

1. Files and knowledge can be uploaded without losing the original document.
2. New knowledge waits for admin review before retrieval.
3. Published answers cite the knowledge version and original source.
4. Operators can see pending review, parse failures, similar documents, and source files from the dashboard.

## Approach

Use the existing lightweight schema and add narrowly scoped fields/tables:

- Extend `knowledge_documents` with publication state and version metadata.
- Extend `knowledge_source_files` with parse status and linked document metadata.
- Add version snapshots for published knowledge.
- Add conflict/similarity records for review queues.
- Keep file bytes on disk; store only paths and metadata in the database.

## Backend Design

### Original File Actions

- Add a protected backend endpoint to download a source file by `source_file_id`.
- Reuse existing permission checks before returning a file.
- Keep the current copy-path behavior in the frontend.
- Download should fail with 404 if the file path does not exist and 403 if the actor cannot access it.

### Review Workflow

New uploaded knowledge defaults to:

- `review_status = pending_review`
- `publication_status = draft`
- `index_status = pending_review`

Admin publish action:

- Validates parsed content is present.
- Sets `review_status = approved`.
- Sets `publication_status = published`.
- Increments `current_version`.
- Creates a `knowledge_document_versions` snapshot.
- Rebuilds chunks/index for retrieval.

Rejected knowledge:

- Sets `review_status = rejected`.
- Keeps source file and parse metadata.
- Does not appear in `kb_search` or `kb_answer`.

Retrieval rule:

- `kb_search`, `kb_answer`, and source citations only use documents where:
  - `publication_status = published`
  - `review_status = approved`
  - `parse_status = parsed`

Existing documents should be backfilled as approved and published so current users do not lose access.

### Version Management

Add `knowledge_document_versions`:

- `id`
- `document_id`
- `version_number`
- `title`
- `summary`
- `content_text`
- `source_file_id`
- `created_by`
- `created_at`

Answer citations include:

- document title
- chunk id
- document version number
- source file name/path when available

### Similarity And Conflict Detection

First version uses deterministic local checks:

- Similarity: compare title overlap, token overlap, and top retrieval score.
- Conflict: flag when similar documents contain obvious opposing terms such as allow/deny, can/cannot, yes/no, enable/disable, refund/no refund, return/not return.

When importing or publishing:

- Return `similar_documents`.
- Create `knowledge_conflict_reports` when likely conflicts exist.
- Do not block upload automatically; show the warnings in review UI.

### Parse Failure Handling

For PDF/Word/Excel/image parse failure:

- Store original file first.
- Create a knowledge document with:
  - `parse_status = parse_failed`
  - `parse_error`
  - `review_status = pending_review`
  - `publication_status = draft`
  - a short placeholder `content_text`
- Do not index it.
- Frontend shows retry/manual summary actions.

Retry parse action can be added as a backend endpoint, but first implementation can expose the failed record and let an admin manually add content.

### Operations Dashboard

Dashboard API adds:

- today query count
- hit rate
- unanswered count
- pending review count
- parse failed count
- recent source files
- pending review documents
- conflict reports
- popular questions

## Frontend Design

### Operations Home

Top of the app shows compact operational cards:

- Today queries
- Hit rate
- Unanswered questions
- Pending review
- Parse failures
- Latest uploads

Below that:

- Pending review queue
- Conflict warnings
- Recent source files
- Popular questions

### Source Files Page

Add an explicit original files view:

- file name
- storage type
- local path
- upload user
- source channel
- external source account
- parse status
- linked document title
- created time
- actions: copy path, download

### Review UI

Knowledge detail panel shows:

- review status
- publication status
- current version
- source file
- similar documents
- conflict warnings

Admin actions:

- publish
- reject
- rebuild index
- copy original path
- download original

### Initialization Wizard

First screen helper panel for Docker/GitHub users:

- API Key input
- admin actor id
- default global accounts
- Feishu/Weixin account mapping text area

First version stores values locally where appropriate and calls existing account sync endpoints for mappings. It does not rewrite server `.env` from the browser.

## Testing Plan

Backend tests:

- pending review documents are not searchable.
- publishing creates a version snapshot and makes document searchable.
- answer citations include version number.
- parse failures preserve source file records and are not indexed.
- source file download respects permissions.
- similar/conflict detection returns warnings.
- existing documents are treated as published after migration/backfill.

Frontend/build tests:

- TypeScript build passes.
- dashboard handles new metrics.
- source file actions render for rows with source file metadata.
- initialization panel does not require server-side secret writes.

Deployment tests:

- `./scripts/verify.sh`
- `docker compose config`

## Non-Goals

- Full document management system.
- Binary file deduplication.
- Multi-version diff viewer.
- Rich workflow approvals with multiple reviewers.
- Live chat/ticketing/SLA platform.
- Browser-based editing of backend environment files.
