"""Who is acting (architecture D7): the two sources and the header-mode checks, as pure
functions over settings, header values and the peer address."""

from __future__ import annotations

from collections.abc import Callable

from oak_misstatements.config import Settings
from oak_misstatements.identity import plausible, resolve, resolve_partner
from tests.conftest import APP_URL

MakeSettings = Callable[..., Settings]


def test_dev_mode_names_the_configured_user(make_settings: MakeSettings) -> None:
    settings = make_settings(database_url=APP_URL, dev_user=" partner@firm ")
    found = resolve(settings, [], "127.0.0.1")
    assert found.user == "partner@firm"
    assert found.status_code == 200


def test_dev_mode_without_a_user_answers_503(make_settings: MakeSettings) -> None:
    settings = make_settings(database_url=APP_URL, dev_user=None)
    found = resolve(settings, [], "127.0.0.1")
    assert found.user is None
    assert found.status_code == 503
    assert "OAK_DEV_USER" in found.detail


def test_header_mode_takes_the_proxys_header(make_settings: MakeSettings) -> None:
    settings = make_settings(database_url=APP_URL, auth="header", trusted_proxies="10.0.0.5")
    assert resolve(settings, ["reviewer@firm"], "10.0.0.5").user == "reviewer@firm"


def test_header_mode_refuses_an_untrusted_peer(make_settings: MakeSettings) -> None:
    settings = make_settings(database_url=APP_URL, auth="header", trusted_proxies="10.0.0.5")
    found = resolve(settings, ["reviewer@firm"], "192.168.1.9")
    assert found.user is None
    assert found.status_code == 401
    assert "trusted proxy" in found.detail


def test_header_mode_refuses_a_duplicated_blank_or_implausible_header(
    make_settings: MakeSettings,
) -> None:
    settings = make_settings(database_url=APP_URL, auth="header")
    assert resolve(settings, ["a@firm", "b@firm"], "10.0.0.5").status_code == 401
    assert resolve(settings, [], "10.0.0.5").status_code == 401
    assert resolve(settings, ["   "], "10.0.0.5").status_code == 401
    assert resolve(settings, ["bad\x00name"], "10.0.0.5").status_code == 401


def test_header_mode_without_a_proxy_list_believes_any_peer(make_settings: MakeSettings) -> None:
    settings = make_settings(database_url=APP_URL, auth="header")
    assert resolve(settings, ["reviewer@firm"], None).user == "reviewer@firm"


def test_plausible_names() -> None:
    assert plausible("a b@firm")
    assert not plausible("")
    assert not plausible("x" * 255)
    assert not plausible("tab\tname")
    assert not plausible("del\x7f")


def test_the_partner_claim_fails_closed_at_every_step(make_settings: MakeSettings) -> None:
    proxy = "10.0.0.5"
    unavailable = make_settings(database_url=APP_URL, auth="header", trusted_proxies=proxy)
    assert resolve_partner(unavailable, "p@firm", ["partner"], proxy).status_code == 403
    assert "unavailable" in resolve_partner(unavailable, "p@firm", ["partner"], proxy).detail
    # D40: configured, but no proxy address listed: never believed.
    unlisted = make_settings(
        database_url=APP_URL,
        auth="header",
        auth_roles_header="X-Authenticated-Roles",
        partner_role="partner",
    )
    assert unlisted.partner_actions_available() is False
    assert resolve_partner(unlisted, "p@firm", ["partner"], proxy).status_code == 403
    settings = make_settings(
        database_url=APP_URL,
        auth="header",
        trusted_proxies="10.0.0.0/24",
        auth_roles_header="X-Authenticated-Roles",
        partner_role="partner",
    )
    assert settings.partner_actions_available() is True
    assert resolve_partner(settings, "p@firm", ["staff, partner"], proxy).user == "p@firm"
    assert resolve_partner(settings, "p@firm", ["staff"], proxy).status_code == 403
    assert resolve_partner(settings, "p@firm", [], proxy).status_code == 403
    assert resolve_partner(settings, "p@firm", [""], proxy).status_code == 403
    assert resolve_partner(settings, "p@firm", ["partner", "partner"], proxy).status_code == 403
    assert resolve_partner(settings, "p@firm", ["partners"], proxy).status_code == 403
    assert resolve_partner(settings, "p@firm", ["Partner"], proxy).status_code == 403
    assert resolve_partner(settings, "p@firm", ["partner\x00"], proxy).status_code == 403
    # The peer is checked again here, whatever the identity check did.
    for peer in ("203.0.113.9", None, "not-an-address", ""):
        refused = resolve_partner(settings, "p@firm", ["partner"], peer)
        assert refused.status_code == 403, peer
        assert "listed proxy address" in refused.detail
    dev_mode = make_settings(database_url=APP_URL, dev_user="partner@firm")
    assert resolve_partner(dev_mode, "partner@firm", ["partner"], proxy).status_code == 403
