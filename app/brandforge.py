#!/usr/bin/env python3
"""BrandForge Desktop CLI: local setup, scoped work and explicit connected features."""
import argparse
import math
import os
import re
import sys
from typing import Optional

if sys.version_info < (3, 10):
    raise SystemExit('BrandForge OS requires Python 3.10 or newer.')

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from engines.ai_engine import get_engine
from modules.project_manager import ProjectManager
from modules.swarm_director import SwarmDirector
from modules.visual_designer import VisualDesigner
from modules.security import atomic_write_text
from modules.desktop_launcher import run_foreground, start_background, validate_bind

console = Console()


def _active_id(ai):
    return ai.clients.get_active_client().get('client_id', 'default') if ai.clients else 'default'


def _persist_provider(ai, provider):
    if provider not in ai.PROVIDER_MODELS:
        raise ValueError('Unknown provider.')
    if not ai.update_configuration({'provider': provider, 'model': ai.PROVIDER_MODELS[provider]}):
        raise RuntimeError(ai.settings_error or 'Provider preference could not be saved.')


def _parse_spend(raw):
    value = str(raw or '').strip()
    if not value:
        return 0.0
    match = re.fullmatch(r'\$?\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)\s*(?:/mo(?:nth)?)?', value, re.I)
    if not match:
        raise ValueError('Enter a non-negative amount such as 200 or $1,200/mo.')
    number = float(match[1].replace(',', ''))
    if not math.isfinite(number) or number > 1_000_000:
        raise ValueError('Monthly spend must be between 0 and 1,000,000.')
    return number


def _capability_line():
    import importlib.util
    caps = ['Six-stage drafting', '21 tools', 'Local SQLite/Markdown memory', 'Desktop dashboard']
    # Merely finding Chroma must not advertise a deliberately disabled feature.
    for module, label in [('playwright', 'Browser-audit integration'), ('telegram', 'Telegram integration')]:
        try:
            if importlib.util.find_spec(module):
                caps.append(label)
        except (ImportError, ValueError):
            pass
    return '[dim]' + ' • '.join(caps) + '[/dim]'


def display_banner(clients=None):
    active = clients.get_active_client() if clients else {'client_name': 'Default Studio'}
    console.print(Panel('[bold gold1]BRANDFORGE OS[/bold gold1]\n'
                        '[bold]Campaign drafts you review and control[/bold]\n'
                        f"Active brand: {escape(str(active.get('client_name', 'Default Studio')))}\n"
                        + _capability_line(), border_style='gold1'))


def _show_response(text, title='BrandForge response'):
    console.print(Panel(Markdown(str(text)), title=title, border_style='gold1'))


def run_free_command_mode(ai, initial_prompt: Optional[str] = None):
    console.print('[dim]Use the configured text engine. Connected tools/providers may send requests. Type exit to return.[/dim]')
    if initial_prompt:
        _show_response(ai.generate_text(initial_prompt, client_id=_active_id(ai)))
        if getattr(ai,"memory_saved",True) is False: console.print("[yellow]This response was not completely saved to memory.[/yellow]")
        return
    while True:
        message = Prompt.ask('Message').strip()
        if not message or message.lower() in ('exit', 'quit', 'back', '0'):
            return
        with Progress(SpinnerColumn(), TextColumn('[cyan]Drafting…'), console=console, transient=True) as progress:
            progress.add_task('draft', total=None)
            answer = ai.generate_text(message, client_id=_active_id(ai))
        _show_response(answer)
        if getattr(ai,"memory_saved",True) is False: console.print("[yellow]This response was not completely saved to memory.[/yellow]")


def run_swarm_campaign(ai, pm, product_name, industry, target_audience, key_benefits, campaign_name, lang='en'):
    client_id = _active_id(ai)
    console.print(f'[bold]Creating draft: {escape(str(campaign_name))}[/bold]')
    with Progress(SpinnerColumn(), TextColumn('[cyan]Assembling the campaign…'), console=console, transient=True) as progress:
        progress.add_task('campaign', total=None)
        result = SwarmDirector(ai).execute_swarm_campaign(product_name, industry, target_audience, key_benefits,
                                                          client_id=client_id, lang=lang)
    folder = pm.save_campaign(campaign_name, result['strategy_data'], result['copy_data'], result['visual_files'],
                              client_id=client_id, analysis_data=result.get('analysis_data', {}), lang=lang)
    console.print(f'[green]Draft saved: {escape(folder)}[/green]')
    # Report files actually written, not a hardcoded list of promised outputs.
    table = Table(title='Saved deliverables'); table.add_column('File')
    for name in sorted(os.listdir(folder)):
        if os.path.isfile(os.path.join(folder, name)):
            table.add_row(escape(name))
    console.print(table)
    return folder


def _start_server_thread(engine=None, port=8000, host='127.0.0.1'):
    return start_background(engine, port=port, host=host)


def run_server_mode(host='127.0.0.1', port=8000, engine=None, open_browser=False):
    validate_bind(host, port)
    value = f'[{host}]' if ':' in host else host
    console.print(f'[bold]Desktop dashboard: http://{value}:{port}/[/bold]')
    console.print('[dim]Loopback only. Keep this terminal open; Ctrl+C stops the server.[/dim]')
    run_foreground(engine, host=host, port=port, open_browser=open_browser)


def _configure_engine(ai):
    console.print('[1] Groq API  [2] Gemini API  [3] Anthropic API  [4] Ollama endpoint  [5] Offline templates')
    console.print('[dim]Provider accounts, availability and charges vary. Existing settings remain unchanged if you cancel.[/dim]')
    choice = Prompt.ask('Select', choices=['1', '2', '3', '4', '5'], default='5')
    if choice in ('1', '2', '3'):
        provider = {'1': 'groq', '2': 'gemini', '3': 'anthropic'}[choice]
        key = Prompt.ask(f'{provider} API key (blank to cancel)', password=True).strip()
        if not key:
            console.print(f'[yellow]No new key saved. Current provider: {escape(ai.provider)}.[/yellow]')
            return False
        if not ai.save_api_key(key, provider=provider):
            console.print('[red]Settings were not saved. Check key format, disk space and permissions.[/red]')
            return False
    elif choice == '4':
        if not ai.check_ollama_alive():
            console.print('[yellow]Configured Ollama endpoint is unavailable; existing settings were kept.[/yellow]')
            return False
        _persist_provider(ai, 'ollama')
    else:
        _persist_provider(ai, 'offline')
    console.print(f'[green]Provider preference saved: {escape(ai.provider)}.[/green]')
    return True


def run_onboard(ai, pm, lang='en', port=8000, host='127.0.0.1'):
    console.print(Panel('BrandForge setup\nChoose an engine, optionally create a draft, then open the dashboard.', border_style='gold1'))
    _configure_engine(ai)
    console.print(f'[dim]Current text engine: {escape(ai.provider)}. Review connected-feature settings before generating.[/dim]')
    if Prompt.ask('Create a sample with this engine?', choices=['yes', 'no'], default='no') == 'yes':
        product = Prompt.ask('Product', default='My Product')
        name = Prompt.ask('Campaign name', default='First Campaign')
        run_swarm_campaign(ai, pm, product, 'General', 'Customers', 'Add approved benefits', name, lang)
    handle = _start_server_thread(ai, port, host)
    if not handle:
        console.print('[yellow]Dashboard did not start. Check whether the port is in use; no unrelated application was opened.[/yellow]')
        return
    try:
        console.print(f'[cyan]Dashboard: {handle.url}[/cyan]')
        try:
            import webbrowser
            webbrowser.open(handle.url)
        except Exception:
            console.print('[yellow]Open the dashboard URL manually.[/yellow]')
        try:
            console.input('Press Enter to stop this dashboard and return… ')
        except (EOFError, KeyboardInterrupt):
            pass
    finally:
        if not handle.stop():
            console.print('[yellow]Shutdown is still pending. Close this process after active work finishes.[/yellow]')


def _menu_action(choice, ai, pm, lang):
    if choice == '1':
        run_free_command_mode(ai)
    elif choice == '2':
        name = Prompt.ask('Campaign name', default='My First Campaign')
        product = Prompt.ask('Product/Brand', default='My Brand')
        industry = Prompt.ask('Industry', default='General')
        audience = Prompt.ask('Audience', default='Customers')
        benefits = Prompt.ask('Approved benefits', default='Add your verified benefit')
        run_swarm_campaign(ai, pm, product, industry, audience, benefits, name, lang)
    elif choice == '3':
        from modules.web_searcher import WebSearcher
        url = Prompt.ask('Public website URL', default='https://example.com')
        result = WebSearcher(data_dir=ai.base_dir).deep_competitor_analysis(url)
        audit = result.get('audit') or {}
        if result.get('error') or audit.get('error') or audit.get('score') is None:
            console.print('[yellow]The inspection did not complete. No clean-site conclusion is available.[/yellow]')
        else:
            body = f"Rule-based score: {audit['score']}/100\nMethod: {audit.get('method', 'unknown')}\n\n"
            body += '\n'.join('- ' + str(item) for item in result.get('recommendations', [])) or 'No recommendations from these limited checks.'
            _show_response(body, 'Public-site checks—not a ranking forecast')
    elif choice == '4':
        table = Table(title='Active-brand memory'); table.add_column('Time'); table.add_column('Role'); table.add_column('Preview')
        for row in ai.memory.get_recent_chat_history(limit=8, client_id=_active_id(ai)):
            table.add_row(escape(row['timestamp'][:19]), escape(row['role']), escape(row['message'][:150]))
        console.print(table)
    elif choice == '5':
        table = Table(title='Tools'); table.add_column('Tool'); table.add_column('Description')
        for tool in ai.tools.list_tools():
            table.add_row(escape(tool['name']), escape(tool['description']))
        console.print(table)
    elif choice == '6':
        result = ai.tools.execute_tool('brand_strategy', {'product': Prompt.ask('Product', default='My Brand'),
                                      'industry': Prompt.ask('Industry', default='General'), 'audience': Prompt.ask('Audience', default='Customers')})
        _show_response(result.get('error') or str(result), 'Brand strategy draft')
    elif choice == '7':
        result = ai.tools.execute_tool('generate_copy', {'product': Prompt.ask('Product', default='My Brand'),
                                      'benefits': Prompt.ask('Approved benefits'), 'audience': Prompt.ask('Audience', default='Customers')})
        _show_response(result.get('copy') or result.get('error') or str(result), 'Copy draft')
    elif choice == '8':
        product = Prompt.ask('Product', default='My Brand'); headline = Prompt.ask('Headline')
        active = ai.clients.get_active_client()
        svg = VisualDesigner(ai).generate_hero_banner_svg(product, headline, primary_color=active.get('primary_color', '#E8B54A'), secondary_color=active.get('secondary_color', '#0F172A'))
        path = os.path.join(ai.base_dir, 'output', 'visual_preview.svg')
        atomic_write_text(path, svg)
        console.print(f'[green]SVG saved: {escape(path)}[/green]')
    elif choice == '9':
        rows = pm.list_campaigns()
        if not rows:
            console.print('No campaigns yet.')
        else:
            table = Table(title='Campaigns'); table.add_column('Campaign'); table.add_column('Product'); table.add_column('Files')
            for row in rows[:20]:
                table.add_row(escape(row['name']), escape(str(row.get('product', ''))), str(row.get('files', 0)))
            console.print(table)
            console.print(f'[dim]Data folder: {escape(pm.base_dir)}[/dim]')
    elif choice == '10':
        _configure_engine(ai)
    elif choice == '11':
        run_server_mode(engine=ai)
    elif choice == '12':
        table = Table(title='Client brands'); table.add_column('Name'); table.add_column('Industry'); table.add_column('ID')
        for row in ai.clients.list_clients():
            table.add_row(escape(row['client_name']), escape(row.get('industry', '')), escape(row['client_id']))
        console.print(table)
        if Prompt.ask('Add a brand?', choices=['yes', 'no'], default='no') == 'yes':
            data = {'client_name': Prompt.ask('Client name'), 'industry': Prompt.ask('Industry', default='General'),
                    'tone_of_voice': Prompt.ask('Tone', default='Clear, specific'), 'primary_color': Prompt.ask('Primary hex', default='#E8B54A'),
                    'secondary_color': Prompt.ask('Secondary hex', default='#0F172A')}
            client_id, _ = ai.clients.save_named_client(data)
            console.print(f'[green]Brand saved as {escape(client_id)}. Activate it in the dashboard.[/green]')
    elif choice == '13':
        from modules.audit_scorecard import AuditScorecard
        from modules.web_searcher import WebSearcher
        brand = Prompt.ask('Brand name', default='My Brand')
        url = Prompt.ask('Website URL (blank for no web inspection)', default='')
        spend = _parse_spend(Prompt.ask('Assumed monthly tool spend ($)', default='200'))
        site = WebSearcher(data_dir=ai.base_dir).browser_audit(url, take_screenshot=False) if url else None
        active = ai.clients.get_active_client()
        html = AuditScorecard(ai).generate_scorecard_html(brand, url=url, site_audit=site, monthly_spend=spend,
                primary_color=active.get('primary_color', '#E8B54A'), secondary_color=active.get('secondary_color', '#0F172A'), brand_text=active.get('agency_brand', 'BrandForge OS'))
        path = os.path.join(ai.base_dir, 'output', 'audit_scorecard.html')
        atomic_write_text(path, html)
        console.print(f'[green]Scorecard saved: {escape(path)}[/green]')
    else:
        run_free_command_mode(ai, initial_prompt=choice)


def interactive_menu(ai, pm, lang='en'):
    while True:
        console.print('[bold gold1]BrandForge Desktop[/bold gold1]\n'
                      '[1] Chat  [2] Campaign  [3] Website checks  [4] Active-brand memory\n'
                      '[5] Tools  [6] Brand strategy  [7] Copy  [8] Visual\n'
                      '[9] Campaigns  [10] Engine settings  [11] Dashboard  [12] Brands\n'
                      '[13] Cost/website scorecard  [0] Exit')
        try:
            choice = Prompt.ask('Choose an action or enter a message', default='1').strip()
            if choice == '0':
                return
            _menu_action(choice, ai, pm, lang)
        except (EOFError, KeyboardInterrupt):
            return
        except (ValueError, OSError, RuntimeError):
            console.print('[red]The action was not completed. Check the input and local storage; no successful save is being claimed.[/red]')


def update_notice(ai=None):
    try:
        from modules.update_check import allowed, check_for_update
        from version_info import __version__
        ai = ai or get_engine(provider=None)
        consent = ai.config.get('update_check') == 'on'
        if not allowed(consent):
            return
        result = check_for_update(__version__, timeout=3, consent=consent)
        if result.get('update_available'):
            console.print(f"[bold]Update available:[/bold] {escape(str(result['latest']))} — review the release before installing.")
    except Exception:
        return  # Optional notice never prevents local work.


def main():
    parser = argparse.ArgumentParser(description='BrandForge Desktop: draft, review and export')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--server', action='store_true')
    mode.add_argument('--onboard', action='store_true')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--open-browser', action='store_true')
    parser.add_argument('--provider', choices=['offline','ollama','gemini','groq','anthropic','openrouter','deepseek','kimi','xai_grok'])
    parser.add_argument('--lang', default='en', choices=['en','hi','ur','es','pt'])
    parser.add_argument('--product'); parser.add_argument('--campaign-name')
    args = parser.parse_args()
    if bool(args.product) != bool(args.campaign_name) or ((args.server or args.onboard) and args.product):
        parser.error('--product and --campaign-name must be supplied together, separately from server/onboarding modes.')
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    if args.open_browser and not args.server:
        parser.error('--open-browser is a server option; onboarding opens its own managed dashboard.')
    if args.server or args.onboard:
        try: validate_bind(args.host, args.port)
        except ValueError as exc: parser.error(str(exc))
    from modules.net_audit import install
    install()
    ai = None
    try:
        ai = get_engine(provider=args.provider); pm = ProjectManager(base_dir=ai.base_dir)
        display_banner(ai.clients)
        if not args.server:
            update_notice(ai)
        if args.onboard: run_onboard(ai, pm, args.lang, args.port, args.host)
        elif args.server: run_server_mode(args.host, args.port, ai, args.open_browser)
        elif args.product: run_swarm_campaign(ai, pm, args.product, 'General', 'Customers', 'Add approved benefits', args.campaign_name, args.lang)
        else: interactive_menu(ai, pm, args.lang)
        return 0
    except (OSError, ValueError, RuntimeError):
        console.print('[red]The operation was not completed. Check input, settings, permissions and available disk space.[/red]')
        return 1
    finally:
        if getattr(ai, 'memory', None):
            ai.memory.close()


if __name__ == '__main__':
    raise SystemExit(main())
