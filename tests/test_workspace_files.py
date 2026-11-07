import base64
from uuid import uuid4
from unittest.mock import Mock
import threading
from delta_agent.commands import CommandExecutor
from delta_contracts.workspace_files import FileStore


def test_agent_workspace_policy_and_sources(tmp_path):
    root=tmp_path/'sources';root.mkdir();(root/'test.txt').write_text('hello')
    adapter=Mock();adapter.capabilities=['workspace_files','search_files','read_file']
    executor=CommandExecutor(adapter,[str(root)],permission=lambda _: 'allow')
    executor.file_store=FileStore(tmp_path/'workspaces');key=str(uuid4())
    def call(action,payload):return executor.execute({'command_id':'test','action':action,'payload':payload})
    found=call('search_files',{'query':'test.txt'})
    assert found['success'] and len(found['data']['matches'])==1
    source=call('read_file',{'path':str(root/'test.txt')})
    assert base64.b64decode(source['data']['content_base64'])==b'hello'
    payload={'workspace_id':key,'operation':'write','path':'index.html','content_base64':'aGVsbG8='}
    assert call('workspace_files',payload)['success']
    assert call('workspace_files',payload)['error_code']=='FILE_CONFLICT'
    assert not call('workspace_files',{**payload,'path':'../escape.txt'})['success']
    executor.permission=lambda _: 'deny'
    assert call('read_file',{'path':str(root/'test.txt')})['error_code']=='COMMAND_DENIED'
    executor.permission=lambda _: 'ask';executor.confirm=Mock(return_value=False)
    assert call('workspace_files',{**payload,'operation':'list'})['error_code']=='APPROVAL_DECLINED'
    executor.permission=lambda _: 'allow'
    cancel=threading.Event();cancel.set()
    assert executor.execute({'command_id':'expired','action':'workspace_files','payload':payload},cancel)['error_code']=='COMMAND_EXPIRED'
