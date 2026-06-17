# app/services/yaml_builder.py
from io import StringIO

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.nlu import Intent

RASA_VERSION = "3.1"


def _literal_str_representer(dumper: yaml.Dumper, data: str):
    """Render multi-line strings as block scalars for readability."""
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


class _RasaDumper(yaml.SafeDumper):
    pass


_RasaDumper.add_representer(str, _literal_str_representer)


def _dump(data: dict) -> str:
    buf = StringIO()
    yaml.dump(
        data,
        buf,
        Dumper=_RasaDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    return buf.getvalue()


def _load_intents(db: Session) -> list[Intent]:
    return db.scalars(
        select(Intent)
        .options(
            selectinload(Intent.examples),
            selectinload(Intent.responses),
        )
        .order_by(Intent.name)
    ).all()


def build_nlu_yaml(db: Session) -> str:
    intents = _load_intents(db)

    nlu_items = []
    for intent in intents:
        if not intent.examples:
            continue
        examples_block = "".join(f"- {ex.text}\n" for ex in intent.examples)
        nlu_items.append({"intent": intent.name, "examples": examples_block})

    return _dump({"version": RASA_VERSION, "nlu": nlu_items})


def build_domain_yaml(db: Session) -> str:
    intents = _load_intents(db)
    intent_names = [intent.name for intent in intents]

    responses_block: dict = {}
    for intent in intents:
        if intent.responses:
            responses_block[f"utter_{intent.name}"] = [
                {"text": r.text} for r in intent.responses
            ]

    return _dump({
        "version": RASA_VERSION,
        "intents": intent_names,
        "responses": responses_block,
        "session_config": {
            "session_expiration_time": 60,
            "carry_over_slots_to_new_session": True,
        },
    })



def build_rules_yaml(db: Session) -> str:
    intents = _load_intents(db)

    rules = [
        {
            "rule": f"Respond to {intent.name}",
            "steps": [
                {"intent": intent.name},
                {"action": f"utter_{intent.name}"},
            ],
        }
        for intent in intents
    ]

    return _dump({"version": RASA_VERSION, "rules": rules})