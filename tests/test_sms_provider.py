from app.services.sms.console_provider import ConsoleSmsProvider
from app.services.sms import get_sms_provider


def test_console_provider_always_succeeds():
    provider = ConsoleSmsProvider()
    result = provider.send("+2250712345678", "Bonjour !", "PMEPMI")
    assert result.success is True
    assert result.provider == "console"
    assert result.provider_message_id.startswith("console-")


def test_factory_returns_console_provider_in_tests(app):
    provider = get_sms_provider()
    assert provider.name == "console"


def test_send_bulk_default_implementation():
    provider = ConsoleSmsProvider()
    results = provider.send_bulk(["+2250712345678", "+2250712345679"], "Promo", "PMEPMI")
    assert len(results) == 2
    assert all(r.success for r in results)
