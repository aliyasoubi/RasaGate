# Deprecated / unused code (kept for reference only)

These two files were found in `app/services/` but **never imported by any
other module** — confirmed via `grep -rn` across the whole `app/` package.
They also don't compile against the current schema, so importing them would
crash immediately:

## `task_repository.py` / `training_task_service.py`

Both reference things that don't exist in `app/models/nlu.py`:

- `TaskStatus.PENDING`, `TaskStatus.TRAINING`, `TaskStatus.COMPLETED`
  (uppercase) — the real enum is lowercase: `pending`, `processing`,
  `success`, `failed`. There is no `TRAINING` or `COMPLETED` value at all.
- `TrainingTask.id` — the real primary key column is `task_id`.
- `TrainingTask.metadata` and `TrainingTask.model_path` — neither column
  exists on the real model.

This looks like an earlier, abandoned attempt at a repository/service layer
for training tasks, superseded by the working implementation that's
actually wired up: `app/api/v1/training.py` (endpoint + concurrency check)
and `app/services/training_orchestrator.py` (the pipeline itself), which
query `TrainingTask` directly via SQLAlchemy.

**If you want a repository/service layer for training tasks** (reasonable —
`training.py`'s `_has_active_task()` helper and the orchestrator's
raw queries could be consolidated), rewrite these against the real model:
`TrainingTask.task_id`, `TaskStatus.pending` / `.processing` / `.success` /
`.failed`, and drop the `metadata`/`model_path` fields (or add real columns
for them if you want that capability — currently the trained model's path
isn't persisted anywhere in the DB, only in the training-completed log
line and webhook payload).

Kept here rather than deleted so nothing is lost, but excluded from
`app/services/` so they can't accidentally get imported and crash.
