import json
from unittest.mock import Mock

import pytest
from app.agent.state import create_initial_state
from app.agent.nodes import parser
from app.api.websocket import WorkflowRunner
from app.storage.auth_repository import AuthRepository
from app.storage.memory import memory_store
from app.contracts.project_input import validate_spec


def fake_llm(monkeypatch,style):
    client=Mock()
    client.generate.return_value=json.dumps(dict(topic='湿地保护',audience='通用',page_count=8,style=style,style_reason='自然主题契合生态内容',needs_cover=True,needs_toc=True,needs_summary=True,needs_chart=False,notes=''))
    monkeypatch.setattr(parser,'get_llm_client',lambda _:client)
    return client


def test_auto_style_single_parse_call_and_manual_preservation(monkeypatch):
    client=fake_llm(monkeypatch,'自然清新')
    state=parser.parser_node(create_initial_state('auto',{'style':'自动'},'介绍湿地保护'))
    assert state['project'].spec['style']=='自然清新'
    assert state['style_selection']['mode']=='auto' and not state['style_selection']['fallback']
    assert client.generate.call_count==1
    assert '自然清新' in client.generate.call_args.kwargs['prompt']
    manual=parser.parser_node(create_initial_state('manual',{'style':'深海蓝金'},'介绍湿地保护'))
    assert manual['project'].spec['style']=='深海蓝金' and not manual.get('style_selection')
    fake_llm(monkeypatch,'未知主题')
    fallback=parser.parser_node(create_initial_state('fallback',{'style':'自动'},'内容'))
    assert fallback['project'].spec['style']=='商务简约' and fallback['style_selection']['fallback']
    assert not fallback['errors']
    assert validate_spec({'style':'自动'})=={'style':'自动'}


@pytest.mark.asyncio
async def test_auto_result_persists_through_websocket_settings_merge(monkeypatch,tmp_path):
    monkeypatch.setenv('FOLIO_DB',str(tmp_path/'auto.db'))
    from app.storage.sqlite_repository import ProjectRepository
    monkeypatch.setattr(memory_store,'_repository',ProjectRepository())
    uid=AuthRepository().register('automatic@example.test','Automatic-password-123','Auto')
    assert AuthRepository().user(uid)
    client=fake_llm(monkeypatch,'自然清新')
    project=WorkflowRunner.create_project({'style':'自动','page_count':4},'湿地保护',owner_id=uid)
    async def send(_): pass
    runner=WorkflowRunner(project['id'],send)
    await runner.cmd_parse_input(project['id'])
    saved=memory_store.get_project(project['id'])
    assert saved['spec']['style']=='自然清新' and saved['spec']['page_count']==4
    assert saved['style_selection']['style']=='自然清新'
    assert client.generate.call_count==1
    assert ProjectRepository().load_all()[project['id']]['style_selection']==saved['style_selection']
    assert WorkflowRunner.create_project({'topic':'新演示'},owner_id=uid)['spec']['style']=='自动'
    memory_store._projects.clear()
