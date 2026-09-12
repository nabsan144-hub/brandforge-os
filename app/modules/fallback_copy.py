"""Grounded offline templates shared with Cloud, not model-generated research."""
import json
import re
from pathlib import Path
from functools import lru_cache


@lru_cache(maxsize=1)
def bundles():
    return json.loads((Path(__file__).resolve().parents[1]/'brandforge_assets'/'fallbacks.json').read_text(encoding='utf-8'))


def fallback(stage, context, lang='en'):
    b = bundles().get(lang, bundles()['en'])
    benefits = context.get('benefits') or context.get('key_benefits') or b['no_benefits']
    if isinstance(benefits, list): benefits = ', '.join(benefits)
    fields = {'product': context.get('product') or 'Your product', 'industry': context.get('industry') or 'your market',
              'audience': context.get('audience') or context.get('target_audience') or 'your customers', 'benefits': benefits,
              'b1': re.split(r'[,;\n]', benefits)[0].strip(), 'offer': context.get('offer') or ''}
    for key in ('cta','tone','proof','avoided','url'):
        fields[key] = context.get(key) or b[key]
    fields['problem'] = b['problem'].format_map(fields)
    if lang == 'en':
        industry = fields['industry'].lower()
        if re.search(r'coffee|food|café|cafe|beverage', industry): fields['problem'] = 'Finding a food or drink option that fits your preferences and routine.'
        elif re.search(r'service|consult|repair|salon', industry): fields['problem'] = 'Finding a service whose scope, availability and terms are clear.'
        elif re.search(r'saas|software|app|technology', industry): fields['problem'] = 'Finding a tool that fits the workflow without unnecessary complexity.'
        elif re.search(r'retail|shop|fashion', industry): fields['problem'] = 'Choosing a product with clear specifications, sizing and purchase terms.'
        elif re.search(r'health|medical|supplement', industry): fields['problem'] = 'Finding reliable information without unsupported health promises.'
    return '\n'.join(line.rstrip() for line in b[stage].format_map(fields).split('\n'))
