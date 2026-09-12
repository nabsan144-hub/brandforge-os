"""Owner scenario calculator; no network or invented provider prices.
Usage: python scripts/unit_economics.py inputs.json
Required input values are nonnegative USD numbers, except refund_fraction 0..1.
"""
import argparse
import json
from decimal import Decimal, InvalidOperation

FIELDS = ('revenue_usd', 'completed_packs', 'cost_per_pack_usd', 'payment_fee_usd',
          'hosting_usd', 'support_hours', 'support_hourly_usd', 'acquisition_usd',
          'refund_fraction', 'maintenance_reserve_usd')


def calculate(data):
    if not isinstance(data, dict) or set(data) != set(FIELDS):
        raise ValueError('Supply exactly these fields: ' + ', '.join(FIELDS))
    values = {}
    for key in FIELDS:
        if isinstance(data[key], bool):
            raise ValueError('Boolean is not a cost: ' + key)
        try:
            number = Decimal(str(data[key]))
        except InvalidOperation as error:
            raise ValueError('Invalid number: ' + key) from error
        if not number.is_finite() or number < 0 or number > Decimal('1000000000'):
            raise ValueError('Nonnegative finite bounded number required: ' + key)
        values[key] = number
    if values['refund_fraction'] > 1 or values['completed_packs'] % 1:
        raise ValueError('Refund fraction must be 0..1 and completed packs an integer.')
    v = values
    net = v['revenue_usd'] * (1-v['refund_fraction'])
    costs = (v['completed_packs']*v['cost_per_pack_usd'] + v['payment_fee_usd'] +
             v['hosting_usd'] + v['support_hours']*v['support_hourly_usd'] +
             v['acquisition_usd'] + v['maintenance_reserve_usd'])
    money = lambda x: str(x.quantize(Decimal('.01')))
    return {'net_after_assumed_refunds_usd': money(net), 'modeled_cost_usd': money(costs),
            'modeled_contribution_usd': money(net-costs),
            'modeled_cost_per_completed_pack_usd': money(costs/v['completed_packs']) if v['completed_packs'] else None,
            'notice': 'Hypothetical scenario, not audited profit. Use actual invoices, include failed/retried work in cost per completed pack, and separately account for taxes, overhead and liabilities.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs')
    args = parser.parse_args()
    try:
        with open(args.inputs, encoding='utf-8') as handle:
            result = calculate(json.load(handle))
        print(json.dumps(result, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')
