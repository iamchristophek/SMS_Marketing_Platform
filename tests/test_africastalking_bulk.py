import requests

from app.services.sms.africastalking_provider import AfricasTalkingProvider


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
        self.text = str(json_data)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


def test_send_bulk_makes_a_single_request_and_matches_results_by_number(monkeypatch):
    calls = []

    def fake_post(url, data=None, headers=None, timeout=None):
        calls.append(data)
        return FakeResponse(
            {
                "SMSMessageData": {
                    "Recipients": [
                        {"number": "+2250700000002", "status": "Success", "messageId": "id-2"},
                        {"number": "+2250700000001", "status": "Success", "messageId": "id-1"},
                    ]
                }
            }
        )

    monkeypatch.setattr(requests, "post", fake_post)

    provider = AfricasTalkingProvider(username="demo", api_key="key")
    results = provider.send_bulk(
        ["+2250700000001", "+2250700000002"], "Promo", "PMEPMI"
    )

    assert len(calls) == 1  # un seul appel HTTP pour les deux destinataires
    assert [r.provider_message_id for r in results] == ["id-1", "id-2"]  # ré-associé par numéro, pas par position
    assert all(r.success for r in results)


def test_send_bulk_chunks_large_recipient_lists(monkeypatch):
    calls = []

    def fake_post(url, data=None, headers=None, timeout=None):
        numbers = data["to"].split(",")
        calls.append(numbers)
        return FakeResponse(
            {
                "SMSMessageData": {
                    "Recipients": [
                        {"number": n, "status": "Success", "messageId": f"id-{n}"} for n in numbers
                    ]
                }
            }
        )

    monkeypatch.setattr(requests, "post", fake_post)

    provider = AfricasTalkingProvider(username="demo", api_key="key")
    recipients = [f"+225070000{i:04d}" for i in range(250)]
    results = provider.send_bulk(recipients, "Promo", "PMEPMI")

    assert len(calls) == 2  # 250 destinataires -> 2 lots de 200 max
    assert len(results) == 250
    assert all(r.success for r in results)


def test_send_bulk_marks_missing_recipient_as_failed(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None):
        return FakeResponse({"SMSMessageData": {"Recipients": []}})

    monkeypatch.setattr(requests, "post", fake_post)

    provider = AfricasTalkingProvider(username="demo", api_key="key")
    results = provider.send_bulk(["+2250700000001"], "Promo", "PMEPMI")

    assert results[0].success is False
