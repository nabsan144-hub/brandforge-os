import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('unit_economics', Path(__file__).resolve().parents[2]/'scripts/unit_economics.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def scenario():
    return dict.fromkeys(module.FIELDS, 0)


def test_costs_include_failed_work_estimate_support_refunds_and_maintenance():
    data = scenario()
    data.update(revenue_usd=100, completed_packs=10, cost_per_pack_usd=2,
                support_hours=2, support_hourly_usd=10, refund_fraction=.1, maintenance_reserve_usd=10)
    result = module.calculate(data)
    assert result['modeled_contribution_usd'] == '40.00'
    assert result['modeled_cost_per_completed_pack_usd'] == '5.00'


@pytest.mark.parametrize('bad', [-1, True, 'NaN', 'Infinity', 'not money'])
def test_invalid_inputs_are_not_silently_zero(bad):
    data = scenario()
    data['hosting_usd'] = bad
    with pytest.raises(ValueError):
        module.calculate(data)


def test_no_completed_work_does_not_divide_by_zero():
    assert module.calculate(scenario())['modeled_cost_per_completed_pack_usd'] is None
