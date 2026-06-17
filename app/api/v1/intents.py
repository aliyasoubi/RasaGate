# app/api/v1/intents.py
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import IntentConflictError, IntentNotFoundError, ResourceNotFoundError
from app.db.session import get_db
from app.models.nlu import Example, Intent, Response
from app.schemas.base import SuccessResponse
from app.schemas.nlu import ExampleCreate, ExampleOut, IntentCreate, IntentOut, IntentUpdate, ResponseCreate, ResponseOut, ResponseUpdate

router = APIRouter(prefix="/intents", tags=["intents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_intent_or_404(name: str, db: Session) -> Intent:
    intent = db.scalar(select(Intent).where(Intent.name == name))
    if intent is None:
        raise IntentNotFoundError(name)
    return intent


# ---------------------------------------------------------------------------
# Intent endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=SuccessResponse)
def list_intents(db: Session = Depends(get_db)):
    intents = db.scalars(select(Intent).order_by(Intent.name)).all()
    return SuccessResponse(data=[IntentOut.model_validate(i) for i in intents])


@router.post("/", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
def create_intent(payload: IntentCreate, db: Session = Depends(get_db)):
    intent = Intent(name=payload.name, description=payload.description)
    db.add(intent)

    try:
        db.flush()  # get intent.id before adding children
    except IntegrityError:
        db.rollback()
        raise IntentConflictError(payload.name)

    for text in payload.examples:
        db.add(Example(text=text, intent_id=intent.id))

    for text in payload.responses:
        db.add(Response(text=text, intent_id=intent.id))

    db.commit()
    db.refresh(intent)

    return SuccessResponse(
        data=IntentOut.model_validate(intent),
        message="Intent created successfully.",
    )


@router.get("/{intent_name}", response_model=SuccessResponse)
def get_intent(intent_name: str, db: Session = Depends(get_db)):
    intent = _get_intent_or_404(intent_name, db)
    return SuccessResponse(data=IntentOut.model_validate(intent))


@router.patch("/{intent_name}", response_model=SuccessResponse)
def update_intent(intent_name: str, payload: IntentUpdate, db: Session = Depends(get_db)):
    intent = _get_intent_or_404(intent_name, db)
    if payload.description is not None:
        intent.description = payload.description
    db.commit()
    db.refresh(intent)
    return SuccessResponse(data=IntentOut.model_validate(intent))


@router.delete("/{intent_name}", response_model=SuccessResponse)
def delete_intent(intent_name: str, db: Session = Depends(get_db)):
    intent = _get_intent_or_404(intent_name, db)
    db.delete(intent)
    db.commit()
    return SuccessResponse(message=f"Intent '{intent_name}' and all linked data deleted.")


# ---------------------------------------------------------------------------
# Example sub-resource
# ---------------------------------------------------------------------------

@router.post(
    "/{intent_name}/examples",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_example(intent_name: str, payload: ExampleCreate, db: Session = Depends(get_db)):
    intent = _get_intent_or_404(intent_name, db)
    example = Example(text=payload.text, intent_id=intent.id)
    db.add(example)
    db.commit()
    db.refresh(example)
    return SuccessResponse(
        data=ExampleOut.model_validate(example),
        message="Example added.",
    )


@router.put(
    "/{intent_name}/examples/{example_id}",
    response_model=SuccessResponse,
)
def update_example(
    intent_name: str,
    example_id: int,
    payload: ExampleCreate,
    db: Session = Depends(get_db),
):
    intent = _get_intent_or_404(intent_name, db)
    example = db.scalar(
        select(Example).where(
            Example.id == example_id, Example.intent_id == intent.id
        )
    )
    if example is None:
        raise ResourceNotFoundError("example", example_id)

    example.text = payload.text
    db.commit()
    db.refresh(example)
    return SuccessResponse(data=ExampleOut.model_validate(example))


@router.delete("/{intent_name}/examples/{example_id}", response_model=SuccessResponse)
def delete_example(intent_name: str, example_id: int, db: Session = Depends(get_db)):
    intent = _get_intent_or_404(intent_name, db)
    example = db.scalar(
        select(Example).where(
            Example.id == example_id, Example.intent_id == intent.id
        )
    )
    if example is None:
        raise ResourceNotFoundError("example", example_id)

    db.delete(example)
    db.commit()
    return SuccessResponse(message=f"Example {example_id} deleted.")


# ---------------------------------------------------------------------------
# Response sub-resource
# ---------------------------------------------------------------------------

@router.post(
    "/{intent_name}/responses",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_response(intent_name: str, payload: ResponseCreate, db: Session = Depends(get_db)):
    intent = _get_intent_or_404(intent_name, db)
    response = Response(text=payload.text, intent_id=intent.id)
    db.add(response)
    db.commit()
    db.refresh(response)
    return SuccessResponse(
        data=ResponseOut.model_validate(response),
        message="Response variation added.",
    )


@router.put(
    "/{intent_name}/responses/{response_id}",
    response_model=SuccessResponse,
)
def update_response(
    intent_name: str,
    response_id: int,
    payload: ResponseUpdate,
    db: Session = Depends(get_db),
):
    intent = _get_intent_or_404(intent_name, db)
    response = db.scalar(
        select(Response).where(
            Response.id == response_id, Response.intent_id == intent.id
        )
    )
    if response is None:
        raise ResourceNotFoundError("response", response_id)

    response.text = payload.text
    db.commit()
    db.refresh(response)
    return SuccessResponse(data=ResponseOut.model_validate(response))


@router.delete(
    "/{intent_name}/responses/{response_id}",
    response_model=SuccessResponse,
)
def delete_response(intent_name: str, response_id: int, db: Session = Depends(get_db)):
    intent = _get_intent_or_404(intent_name, db)
    response = db.scalar(
        select(Response).where(
            Response.id == response_id, Response.intent_id == intent.id
        )
    )
    if response is None:
        raise ResourceNotFoundError("response", response_id)

    db.delete(response)
    db.commit()
    return SuccessResponse(message=f"Response {response_id} deleted.")