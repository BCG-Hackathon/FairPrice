import re
import string

import pytest

from app.i18n import CATALOGS, t
from app.i18n.en import MESSAGES as EN
from app.models import Language

# GSM-7 basic charset (the subset we allow in SMS/USSD strings).
GSM7 = set(string.ascii_letters + string.digits + " \n@$_!\"#%&'()*+,-./:;<=>?")


@pytest.mark.parametrize("lang", [Language.SW, Language.ACH])
def test_translations_use_same_placeholders_as_english(lang):
    for key, text in CATALOGS[lang].items():
        assert key in EN, f"{lang}: unknown key {key}"
        assert set(re.findall(r"{(\w+)}", text)) == set(re.findall(r"{(\w+)}", EN[key])), key


@pytest.mark.parametrize("lang", list(Language))
def test_strings_are_gsm7_safe(lang):
    for key, text in CATALOGS[lang].items():
        bad = {ch for ch in text.replace("{", "").replace("}", "") if ch not in GSM7}
        assert not bad, f"{lang}:{key} has non GSM-7 characters {bad}"


def test_missing_key_falls_back_to_english():
    assert t(Language.ACH, "brief.subscribed") == EN["brief.subscribed"]
