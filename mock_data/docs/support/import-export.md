# Import and export tasks

## Import tasks from CSV

An Owner, Admin, or Member can open a project and select **More > Import CSV**. The file must be UTF-8 encoded and contain a `title` column. Optional columns are `description`, `assignee_email`, `due_date`, and `labels`. Dates use `YYYY-MM-DD`. Separate multiple labels with semicolons. A CSV import is limited to 5,000 rows and 10 MB.

The preview shows invalid rows before import. Rows with an empty title or an invalid date are skipped. If an assignee email does not belong to the workspace, the task is imported without an assignee. Importing the same file twice creates duplicate tasks; imports are not automatically deduplicated.

## Export tasks

An Owner or Admin can select **Settings > Data export > Export tasks**. The export includes task titles, descriptions, assignees, due dates, labels, status, and project names for the workspace. The system emails a download link when the CSV is ready. The link expires after 24 hours. Viewers and Members cannot request a workspace export.

Comments and attachments are not included in CSV exports. Contact the workspace Owner if you need a full data archive.
