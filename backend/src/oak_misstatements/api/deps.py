"""Request-scoped dependencies: a database session, the Spine client, the settings, the
acting user."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from oak_misstatements.config import Settings
from oak_misstatements.errors import ServiceUnavailable
from oak_misstatements.identity import current_partner, current_user
from oak_misstatements.services.spine_client import SpineClient

logger = logging.getLogger(__name__)


def get_session(request: Request) -> Iterator[Session]:
    """One transaction per request: committed when the route returns, rolled back when it
    raises. Routes build their JSON before returning, so nothing is read after the commit.

    The dependency is declared with ``scope="function"`` (``SessionDep``), so the commit
    happens **before** the response is sent. A commit the database refuses therefore fails
    the request with a 503 and is never reported as success (D42): the client must not be
    told a version was recorded when it was not, least of all after the Financial Spine has
    already been asked for a decision.
    """
    factory: sessionmaker[Session] = request.app.state.session_factory
    session = factory()
    try:
        yield session
    except BaseException:
        session.rollback()
        raise
    else:
        try:
            session.commit()
        except SQLAlchemyError as error:
            session.rollback()
            cause: BaseException = getattr(error, "orig", None) or error
            logger.error("commit failed for %s %s: %s", request.method, request.url.path, cause)
            raise ServiceUnavailable(
                f"the database refused the commit ({type(cause).__name__}: {cause}); nothing "
                "was recorded here. If this request asked the Financial Spine to propose or "
                "decide an adjustment, the Spine may already hold it: read the misstatement, "
                "check state_consistency, and repeat the same request to complete it "
                "(architecture D42)"
            ) from error
    finally:
        session.close()


def get_spine(request: Request) -> SpineClient | None:
    client: SpineClient | None = request.app.state.spine_client
    return client


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SessionDep = Annotated[Session, Depends(get_session, scope="function")]
SpineDep = Annotated[SpineClient | None, Depends(get_spine)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
UserDep = Annotated[str, Depends(current_user)]
PartnerDep = Annotated[str, Depends(current_partner)]
