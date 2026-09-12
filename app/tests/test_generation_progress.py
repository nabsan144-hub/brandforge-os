import pytest
from modules import generation_progress as progress


def test_progress_is_bounded_ephemeral_and_omits_private_contents():
    key = progress.start()
    progress.update(key, 'strategy', 'running')
    assert progress.read(key)['stages'] == {'strategy': 'running'}
    progress.update(key, 'secrets', 'running')
    assert set(progress.read(key)) == {'request_id', 'status', 'stages'}
    with pytest.raises(ValueError):
        progress.start(key)
    progress.finish(key, 'completed')
    progress.update(key, 'strategy', 'running')
    assert progress.read(key)['status'] == 'completed'
    assert progress.read('not-a-request') is None
