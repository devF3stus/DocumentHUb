# DocumentHub — Database & Storage Design

## 1. Tables

### `public.profiles`
Stores optional user preferences (such as default OCR language).
- **Primary Key:** `id` (`UUID`), which is also a **Foreign Key** referencing `auth.users(id)` with `ON DELETE CASCADE`.
- **RLS:** Users can only `SELECT`, `INSERT`, and `UPDATE` their own profile (`auth.uid() = id`).

### `public.processing_jobs`
Tracks document processing jobs and metadata (never raw document contents).
- **Primary Key:** `id` (`UUID`, auto-generated).
- **Foreign Key:** `user_id` (`UUID`, nullable) referencing `auth.users(id)`.
  - For **logged-in users**, `user_id` links the job to their account so they can view history.
  - For **guest users**, `user_id` is `NULL`; their files are processed in temporary server directories and deleted immediately after download.
- **RLS:** Authenticated users can only access rows where `auth.uid() = user_id`. Guest rows (`user_id IS NULL`) cannot be queried from the browser.

## 2. Private Storage (`documents` bucket)
- Created with `public = FALSE` so no file has a permanent public URL.
- Files for logged-in users are stored under `<user_id>/<random_uuid>.<ext>`.
- Storage RLS enforces `auth.uid()::text = (storage.foldername(name))[1]`.
- Downloads use **short-lived signed URLs** (e.g., 60 seconds).
