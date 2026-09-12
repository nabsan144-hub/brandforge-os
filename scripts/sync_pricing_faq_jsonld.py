#!/usr/bin/env python3
"""Keep pricing FAQ structured data equal to visible summary/answer content.

Run with --check in CI; without it, replace only the FAQPage JSON-LD block.
"""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


class FAQParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items, self.question, self.answer = [], [], []
        self.in_details = self.in_summary = False

    def handle_starttag(self, tag, attrs):
        if tag == 'details':
            if self.in_details:
                raise ValueError('Nested FAQ details require explicit review')
            self.in_details, self.question, self.answer = True, [], []
        elif self.in_details and tag == 'summary':
            self.in_summary = True
        elif self.in_details and tag in ('p', 'br', 'li'):
            self.answer.append(' ')

    def handle_endtag(self, tag):
        if tag == 'summary':
            self.in_summary = False
        if tag == 'details' and self.in_details:
            clean = lambda words: re.sub(r'\s+', ' ', ''.join(words)).strip()
            q, a = clean(self.question), clean(self.answer)
            if not q or not a:
                raise ValueError('FAQ question or answer is empty')
            self.items.append({'@type': 'Question', 'name': q,
                               'acceptedAnswer': {'@type': 'Answer', 'text': a}})
            self.in_details = False

    def handle_data(self, data):
        if self.in_details:
            (self.question if self.in_summary else self.answer).append(data)


def sync(page, check=False):
    parser = FAQParser()
    parser.feed(page)
    if not parser.items:
        raise ValueError('No visible FAQs found; refusing to erase structured data')
    expected = {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': parser.items}
    matches = []
    for m in re.finditer(r'<script\b[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', page, re.S | re.I):
        data = json.loads(m[1])
        if data.get('@type') == 'FAQPage':
            matches.append((m, data))
    if len(matches) != 1:
        raise ValueError('Expected exactly one FAQPage script')
    m, actual = matches[0]
    if check:
        if actual != expected:
            raise ValueError('FAQ structured data differs from visible content; run the sync script')
        return page
    block = json.dumps(expected, ensure_ascii=False, indent=1).replace('<', '\\u003c')
    return page[:m.start(1)] + '\n' + block + '\n' + page[m.end(1):]


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument('--check', action='store_true')
    check = args.parse_args().check
    path = ROOT / 'sales/pricing.html'
    result = sync(path.read_text(encoding='utf-8'), check)
    if not check:
        path.write_text(result, encoding='utf-8')
    print('Pricing FAQ structured data matches visible content.')


if __name__ == '__main__':
    main()
