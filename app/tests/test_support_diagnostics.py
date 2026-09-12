import json
import support_diagnostics


def test_support_report_excludes_environment_and_user_paths(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'PRIVATE-KEY-SENTINEL')
    monkeypatch.setenv('BRANDFORGE_DATA_DIR', '/private/customer/sentinel')
    report = support_diagnostics.report()
    assert set(report) == {'schema', 'app_version', 'python_version', 'operating_system', 'machine_architecture', 'packages', 'missing_packages', 'notice'}
    assert 'SENTINEL' not in json.dumps(report)
    assert '/private/customer' not in json.dumps(report)


def test_missing_package_is_explicit(monkeypatch):
    def missing(name):
        raise support_diagnostics.PackageNotFoundError(name)
    monkeypatch.setattr(support_diagnostics, 'version', missing)
    assert support_diagnostics.report()['missing_packages'] == list(support_diagnostics.PACKAGES)
