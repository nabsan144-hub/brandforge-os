import socket
import pytest
from modules import public_http as http


def dns(monkeypatch, address='93.184.216.34'):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443))])


@pytest.mark.parametrize('address',['127.0.0.1','10.0.0.1','169.254.169.254','100.64.0.1','::1','::ffff:127.0.0.1','64:ff9b::7f00:1','2002:7f00:1::','224.0.0.1'])
def test_nonpublic_or_translated_addresses_rejected(monkeypatch,address):
    dns(monkeypatch,address)
    with pytest.raises(http.PublicFetchError):http.resolve_public('https://example.test')


def test_actual_connection_is_pinned_and_tls_identity_is_preserved(monkeypatch):
    dns(monkeypatch)
    seen={}
    class Response:
        headers={'content-type':'text/html'};status=200
        def read(self,*a,**k):return b''
        def close(self):seen['closed']=True
    class Pool:
        def __init__(self,**kwargs):seen.update(kwargs)
        def urlopen(self,method,path,**kwargs):seen.update(kwargs);return Response()
        def close(self):pass
    monkeypatch.setattr(http.urllib3,'HTTPSConnectionPool',Pool)
    assert http.fetch_public('https://example.test/path').status_code==200
    assert seen['host']=='93.184.216.34'
    assert seen['assert_hostname']==seen['server_hostname']=='example.test'
    assert seen['cert_reqs']==http.ssl.CERT_REQUIRED
    assert seen['headers']['Host']=='example.test' and seen['redirect'] is False


def test_redirect_is_revalidated_and_never_sent_to_private_ip(monkeypatch):
    dns(monkeypatch);calls=[]
    def exchange(parsed,*args):
        calls.append(parsed.geturl())
        return http.PublicResponse(302,{'location':'http://127.0.0.1/secret'},b'',parsed.geturl())
    monkeypatch.setattr(http,'_exchange',exchange)
    with pytest.raises(http.PublicFetchError):http.fetch_public('https://example.test')
    assert len(calls)==1


def test_stream_is_bounded_before_buffering_and_compression_rejected(monkeypatch):
    dns(monkeypatch);state={'closed':0}
    class Response:
        headers={};status=200
        def read(self,*a,**k):return b'x'*9
        def close(self):state['closed']+=1
    class Pool:
        def __init__(self,**kwargs):pass
        def urlopen(self,*args,**kwargs):return Response()
        def close(self):pass
    monkeypatch.setattr(http.urllib3,'HTTPSConnectionPool',Pool)
    with pytest.raises(http.PublicFetchError):http.fetch_public('https://example.test',max_bytes=8)
    Response.headers={'content-encoding':'gzip'}
    with pytest.raises(http.PublicFetchError):http.fetch_public('https://example.test')
    assert state['closed']==2
