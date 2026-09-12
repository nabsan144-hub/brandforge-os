from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from modules.local_security import LocalSecurityMiddleware, MAX_LOCAL_BODY


def fixture_client():
    app = FastAPI()
    completed = []
    app.add_middleware(LocalSecurityMiddleware, capability='fixture-local-token')
    @app.post('/echo')
    async def echo(request: Request):
        data = await request.body()
        completed.append(len(data))
        return {'bytes': len(data)}
    return TestClient(app), completed


def test_declared_large_body_is_rejected_before_endpoint():
    client, completed = fixture_client()
    r = client.post('/echo', content=b'x', headers={'x-brandforge-token': 'fixture-local-token', 'content-length': str(MAX_LOCAL_BODY + 1)})
    assert r.status_code == 413
    assert completed == []


def test_streamed_body_is_bounded_without_length_header():
    client, completed = fixture_client()
    r = client.post('/echo', content=(b'x' * 1024 * 1024 for _ in range(5)), headers={'x-brandforge-token': 'fixture-local-token'})
    assert r.status_code == 413
    assert completed == []


def test_valid_small_body_still_works():
    client, completed = fixture_client()
    r = client.post('/echo', content=b'hello', headers={'x-brandforge-token': 'fixture-local-token'})
    assert r.status_code == 200 and completed == [5]
