# Standalone Rasa demo project (unused by Rasa Gate)

This folder is the unmodified output of `rasa init` — Rasa's own default
mood-tracker demo bot (`config.yml`, `domain.yml`, `credentials.yml`,
`endpoints.yml`, `data/`, `actions/`, `test_stories.yml`).

**Rasa Gate does not read any file in this folder.** The Gate posts a fully
self-contained training payload straight to Rasa's `/model/train` HTTP
endpoint (see `app/services/training_data_builder.py`), so it never needs a
local Rasa project on disk — the database is the single source of truth.

This is kept only as a reference / fallback:

- If you want to run a plain Rasa server directly (`rasa shell`,
  `rasa train`, `rasa test`) without going through the Gate at all, `cd`
  into this folder and use the normal Rasa CLI.
- If you're customizing `rasa_recipe` / `rasa_assistant_id` /
  `rasa_language` in Gate's `.env`, `config.yml` here shows the full set of
  options (pipeline, policies) those settings stand in for.

Safe to delete if you don't need a standalone Rasa CLI project.
