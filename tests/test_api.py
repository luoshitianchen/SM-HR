from fastapi.testclient import TestClient
from app.main import app
def test_contracts():
 with TestClient(app) as c:
  assert c.get('/health').status_code==200
  assert c.get('/readyz').json()['status']=='ready'
  assert c.get('/api/crypto/status').json()['sm3']=='enabled'
  assert c.get('/api/ops/metrics').status_code==200
