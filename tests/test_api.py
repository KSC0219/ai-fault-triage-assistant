from fastapi.testclient import TestClient

from triage.api import app
from triage.service import TriageService, get_service


def test_endpoints(kb, fault_api):
    app.dependency_overrides[get_service] = lambda: TriageService(kb, fault_api, use_llm=False)
    client = TestClient(app)

    health = client.get("/health").json()
    assert health["status"] == "ok" and health["mode"] == "offline"

    resp = client.post("/triage", json={
        "description": "IPsec tunnel to the branch is down after key rotation",
        "device_name": "fw-blr-edge-01", "create_ticket": True,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["likely_category"] == "vpn_tunnel_down"
    assert body["actions_taken"][0]["result"]["deviceName"] == "fw-blr-edge-01"

    assert client.post("/triage", json={"description": "x"}).status_code == 422
    assert len(client.get("/similar", params={"q": "fan failure overheating", "k": 3}).json()) == 3
    app.dependency_overrides.clear()
