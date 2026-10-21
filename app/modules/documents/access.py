from fastapi import HTTPException

from app.modules.documents.models import Document
from app.modules.users.models import User


def require_document_reader(document: Document | None, actor: User) -> Document:
    if document is None or (document.owner_user_id != actor.id and not actor.is_admin):
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def require_document_owner(document: Document | None, actor: User) -> Document:
    if document is None or document.owner_user_id != actor.id:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
