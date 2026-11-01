"""Explicit AI provider selection; no automatic cross-provider data fallback."""
import asyncio
import os
from openai import AsyncOpenAI
from ai_socket import request

def info():
    return request({'op':'route'}) if os.environ.get('KIAGENT_AI_ENABLED')=='1' else {'provider':'openai'}

async def complete(key,instructions,payload,schema=None,max_tokens=600):
    selected=await asyncio.to_thread(info)
    if selected['provider']=='ollama':
        response=await asyncio.to_thread(request,{'op':'generate','instructions':instructions,'input':payload[:16000],'schema':schema,'max_tokens':max_tokens},85)
        return response['text']
    if selected['provider']!='openai':raise ValueError('Invalid AI provider')
    async with AsyncOpenAI(api_key=key,base_url='https://api.openai.com/v1',timeout=45,max_retries=0) as client:
        options={'model':'gpt-4.1-mini','instructions':instructions,'input':payload,'tools':[],'store':False,'max_output_tokens':max_tokens}
        if schema is not None:options['text']={'format':{'type':'json_schema','name':'package_intent','strict':True,'schema':schema}}
        response=await client.responses.create(**options)
    if response.status!='completed' or not response.output_text.strip():raise ValueError('Incomplete AI answer')
    return response.output_text.strip()
