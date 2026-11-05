"""Migration 0001 applied to oak_misstatements_test: the function and the domain exist and
behave. Skipped, visibly, until OAK_TEST_DATABASE_URL is set (pending decision O2)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.db


def test_append_only_function_exists(db: Connection) -> None:
    found = db.scalar(
        text("SELECT count(*) FROM pg_proc WHERE proname = 'oak_misstatements_append_only'")
    )
    assert found == 1


def test_money_domain_accepts_two_places_and_refuses_three(db: Connection) -> None:
    assert db.scalar(text("SELECT '1234.56'::money_amount")) == Decimal("1234.56")
    assert db.scalar(text("SELECT '-0.01'::money_amount")) == Decimal("-0.01")
    with pytest.raises(DBAPIError):
        db.execute(text("SELECT '1.005'::money_amount"))


def test_money_domain_refuses_nan_and_the_absurd(db: Connection) -> None:
    with pytest.raises(DBAPIError):
        db.execute(text("SELECT 'NaN'::money_amount"))
    with pytest.raises(DBAPIError):
        db.execute(text("SELECT '1000000000000000'::money_amount"))
