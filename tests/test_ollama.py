import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
for name in ('host','tools','src/app'):sys.path.insert(0,str(ROOT/name))
import ai_gateway as gateway
import ai_provider
import ai_admin
import install_ollama as install

class OllamaBudgetTests(unittest.TestCase):
    def test_large_host_keeps_small_upper_bounds(self):
        limits=install.budget(65536,60000,16,100*1024**3)
        self.assertEqual((limits['memory_mib'],limits['cpus'],limits['model']),(4096,2,'qwen3:1.7b'))
        self.assertEqual(limits['parallel'],1)

    def test_small_host_and_insufficient_resources(self):
        limits=install.budget(7800,6000,2,40*1024**3)
        self.assertEqual(limits['model'],'qwen3:0.6b');self.assertEqual(limits['cpus'],.5)
        for values in ((2048,1000,2,40*1024**3),(7800,6000,.5,40*1024**3),(65536,60000,16,2*1024**3)):
            self.assertIsNone(install.budget(*values))

    def test_runtime_patch_preserves_tls_and_is_idempotent(self):
        text=(ROOT/'compose.runtime.yaml').read_text().replace('127.0.0.1:8787:8080','0.0.0.0:9443:8080')
        modified=install.enable_mounts(text)
        self.assertEqual(modified.count('target: /run/kiagent-ai'),2)
        self.assertIn('0.0.0.0:9443:8080',modified)
        self.assertEqual(install.enable_mounts(modified),modified)

    def test_existing_api_is_reused_without_any_mutating_command(self):
        with patch.object(install,'probe',return_value=[{'name':'existing:small','size':1}]),patch.object(install,'output',return_value='') as inspect,patch.object(install,'run',side_effect=AssertionError('Never mutate existing Ollama')):
            found=install.existing();self.assertEqual(found['state'],'existing');self.assertFalse(found['managed'])
            self.assertEqual(inspect.call_count,1)

    def test_existing_stopped_service_is_not_started_or_replaced(self):
        def inspect(command):return 'loaded\n' if command[0].endswith('systemctl') else ''
        with patch.object(install,'probe',return_value=None),patch.object(install,'output',side_effect=inspect),patch.object(install.shutil,'which',return_value=None),patch.object(install,'run',side_effect=AssertionError('Never start existing service')):
            self.assertEqual(install.existing()['state'],'existing_unavailable')

    def test_new_container_has_hard_limits_and_no_public_api_or_gpu(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);limits=install.budget(65536,60000,16,100*1024**3)
            with patch.object(install,'STATE',root/'state'),patch.object(install,'run') as run,patch.object(install,'output',return_value=json.dumps(['ollama/ollama@sha256:'+'a'*64])),patch.object(install,'probe',side_effect=[[],[{'name':limits['model'],'size':1}]]),patch.object(install.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)):
                install.provision(limits,data=root/'models')
            command=run.call_args_list[1].args[0]
            self.assertEqual(command[command.index('--publish')+1],'127.0.0.1:11434:11434')
            self.assertEqual(command[command.index('--memory')+1],'4096m')
            self.assertEqual(command[command.index('--memory-swap')+1],'4096m')
            self.assertEqual(command[command.index('--cpus')+1],'2')
            self.assertNotIn('--gpus',command);self.assertNotIn('--privileged',command)
            self.assertIn('OLLAMA_NUM_PARALLEL=1',command)
            self.assertIn('OLLAMA_MAX_LOADED_MODELS=1',command)

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.server={'endpoint':'http://127.0.0.1:11434','managed':False,'limits':{},'state':'existing'}
        self.selected={'provider':'ollama','model':'existing:small'}
        self.calls=[]
        def config(path,owner=0):return self.server if path.name=='server.json' else self.selected
        self.config=patch.object(gateway,'read',side_effect=config);self.config.start();self.addCleanup(self.config.stop)
        def upstream(endpoint,path,data=None,timeout=3):
            self.calls.append((path,data))
            if path=='/api/tags':return {'models':[{'name':'existing:small','size':10}]}
            return {'done':True,'message':{'content':'Fixture answer'}}
        self.bridge=gateway.Gateway(self.root,upstream)
        self.request={'op':'generate','instructions':'fixture','input':'request','schema':None,'max_tokens':1100}

    def test_shared_instance_gets_no_thread_keepalive_or_model_mutation(self):
        self.assertTrue(self.bridge.handle(self.request)['ok'])
        path,body=self.calls[-1];self.assertEqual(path,'/api/chat')
        self.assertNotIn('keep_alive',body);self.assertNotIn('num_thread',body['options'])
        self.assertEqual(body['options']['num_predict'],512)

    def test_managed_instance_uses_bounded_options(self):
        self.server.update(managed=True,limits={'threads':1,'max_tokens':192})
        self.bridge.handle(self.request);body=self.calls[-1][1]
        self.assertEqual(body['keep_alive'],'30s');self.assertEqual(body['options']['num_thread'],1)
        self.assertEqual(body['options']['num_predict'],192)

    def test_busy_or_oversized_input_never_reaches_model(self):
        self.bridge.inference.acquire()
        self.assertEqual(self.bridge.handle(self.request)['code'],'ai_busy');self.assertFalse(self.calls)
        self.bridge.inference.release()
        with self.assertRaises(ValueError):self.bridge.handle({**self.request,'input':'a'*16001})
        self.assertFalse(self.calls)

    def test_bot_uid_cannot_switch_provider(self):
        with self.assertRaises(ValueError):self.bridge.handle({'op':'select','provider':'openai','model':''},uid=1234)
        self.assertFalse(self.calls)

    def test_cloud_and_embedding_models_are_not_auto_selected(self):
        found=gateway.models({'models':[{'name':'small:cloud','size':1},{'name':'nomic-embed:latest','size':1},{'name':'real:small','size':100}]})
        self.assertEqual([row['name'] for row in found],['real:small'])

class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_ai_works_without_openai_key(self):
        def ipc(data,*args):return {'provider':'ollama'} if data['op']=='route' else {'text':'local answer'}
        with patch.dict(os.environ,{'KIAGENT_AI_ENABLED':'1'}),patch.object(ai_provider,'request',side_effect=ipc),patch.object(ai_provider,'AsyncOpenAI',side_effect=AssertionError('No external fallback')):
            self.assertEqual(await ai_provider.complete('','instructions','request'),'local answer')

    async def test_gateway_failure_never_sends_data_to_openai(self):
        with patch.dict(os.environ,{'KIAGENT_AI_ENABLED':'1'}),patch.object(ai_provider,'request',side_effect=OSError('fixture')),patch.object(ai_provider,'AsyncOpenAI',side_effect=AssertionError('No external fallback')):
            with self.assertRaises(OSError):await ai_provider.complete('fixture-key','instructions','request')

class AdminPrivacyTests(unittest.TestCase):
    def test_unavailable_gateway_fallback_never_returns_extra_json_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'provider.json';path.write_text('{"provider":"ollama","model":"small","secret":"fixture-hidden"}')
            with patch.object(ai_admin,'PROVIDER',path),patch.object(ai_admin,'ai_request',side_effect=OSError()),patch.object(ai_admin.pwd,'getpwnam',return_value=SimpleNamespace(pw_uid=os.getuid())):
                result=ai_admin.handle({'op':'ai_info'})
            self.assertEqual(result['provider'],'ollama');self.assertNotIn('fixture-hidden',json.dumps(result))

    def test_unavailable_gateway_never_follows_provider_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'private';target.write_text('{"provider":"ollama","model":"private-data"}')
            path=root/'provider.json';path.symlink_to(target)
            with patch.object(ai_admin,'PROVIDER',path),patch.object(ai_admin,'ai_request',side_effect=OSError()),patch.object(ai_admin.pwd,'getpwnam',return_value=SimpleNamespace(pw_uid=os.getuid())):
                result=ai_admin.handle({'op':'ai_info'})
            self.assertEqual(result['provider'],'unavailable');self.assertNotIn('private-data',json.dumps(result))

if __name__=='__main__':unittest.main()
