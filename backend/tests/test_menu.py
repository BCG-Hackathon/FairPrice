"""The menu engine is pure, so these tests use a fake data source (no database)."""

from types import SimpleNamespace

from app.i18n import LANGUAGE_MENU
from app.models import Language
from app.services.menu import run_menu


class FakeData:
    def __init__(self):
        self._markets = [SimpleNamespace(code="GULU", name="Gulu"), SimpleNamespace(code="LIRA", name="Lira")]

    def markets(self):
        return self._markets

    def prices_text(self, lang, market, category):
        return f"prices:{lang.value}:{market.code}:{category.value}"

    def brief_text(self, lang):
        return f"brief:{lang.value}"


def test_first_contact_shows_language_picker():
    reply = run_menu([], None, FakeData())
    assert reply.text == LANGUAGE_MENU and not reply.end


def test_choosing_language_saves_it_and_shows_main_menu():
    reply = run_menu(["2"], None, FakeData())
    assert reply.save_language == Language.SW
    assert "Matunda" in reply.text and not reply.end


def test_full_flow_after_language_choice_in_same_session():
    reply = run_menu(["3", "1", "2"], None, FakeData())
    assert reply.end
    assert reply.text == "prices:ach:LIRA:fruits"
    assert reply.save_language == Language.ACH


def test_returning_user_skips_language_picker():
    reply = run_menu(["2", "1"], Language.EN, FakeData())
    assert reply.text == "prices:en:GULU:vegetables_grains"
    assert reply.save_language is None


def test_zero_changes_language():
    assert run_menu(["0"], Language.EN, FakeData()).text == LANGUAGE_MENU
    reply = run_menu(["0", "2"], Language.EN, FakeData())
    assert reply.end and reply.save_language == Language.SW


def test_weekly_brief_option():
    assert run_menu(["4"], Language.SW, FakeData()).text == "brief:sw"


def test_invalid_choices_end_session():
    assert run_menu(["9"], Language.EN, FakeData()).end
    assert run_menu(["1", "7"], Language.EN, FakeData()).end
    assert run_menu(["5"], None, FakeData()).end
