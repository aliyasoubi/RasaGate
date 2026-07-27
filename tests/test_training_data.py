"""Training data builder tests — verify single-document merged YAML."""
import yaml

from app.models.nlu import Example, Intent, Response
from app.services.training_data_builder import build_combined_training_data


def _seed(db):
    greet = Intent(name="greet")
    db.add(greet)
    db.flush()
    db.add(Example(text="hi", intent_id=greet.id))
    db.add(Example(text="hello", intent_id=greet.id))
    db.add(Response(text="Hi there!", intent_id=greet.id))

    # Intent with NO responses — must not generate a rule pointing at a
    # nonexistent utter_ action.
    orphan = Intent(name="smalltalk")
    db.add(orphan)
    db.flush()
    db.add(Example(text="nice weather", intent_id=orphan.id))
    db.commit()


def test_combined_payload_is_single_yaml_document(db_session):
    _seed(db_session)
    payload = build_combined_training_data(db_session)

    docs = list(yaml.safe_load_all(payload))
    assert len(docs) == 1, "Rasa /model/train expects ONE merged YAML document"

    doc = docs[0]
    assert set(doc["intents"]) == {"greet", "smalltalk"}
    assert "utter_greet" in doc["responses"]
    assert doc["responses"]["utter_greet"][0]["text"] == "Hi there!"
    assert any(item["intent"] == "greet" for item in doc["nlu"])


def test_no_rule_for_intent_without_response(db_session):
    _seed(db_session)
    doc = yaml.safe_load(build_combined_training_data(db_session))

    referenced_actions = {
        step["action"]
        for rule in doc["rules"]
        for step in rule["steps"]
        if "action" in step
    }
    # Every action referenced by a rule must exist in responses.
    assert referenced_actions <= set(doc["responses"].keys())
    assert "utter_smalltalk" not in referenced_actions
