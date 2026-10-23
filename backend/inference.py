"""Local inference adapter with streamed text and validated tool calls."""
import json
from typing import Protocol
import httpx

class InferenceProvider(Protocol):
    async def models(self): ...
    async def generate(self, messages, tools, on_token): ...

class OllamaProvider:
    def __init__(self, settings):
        self.settings = settings

    async def models(self):
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            response = await client.get(self.settings.ollama_url + '/api/tags')
            response.raise_for_status()
            return response.json()['models']

    async def generate(self, messages, tools, on_token):
        calls, content, metrics = {}, '', {}
        payload = {'model': self.settings.model, 'messages': messages, 'tools': tools, 'stream': True, 'think': False, 'keep_alive': '5m', 'options': {'num_ctx': 16384, 'num_predict': 2048, 'temperature': 0}}
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10), trust_env=False) as client:
            async with client.stream('POST', self.settings.ollama_url + '/api/chat', json=payload) as response:
                if response.is_error:
                    raw=await response.aread()
                    try:detail=json.loads(raw).get('error','Local model rejected the request')
                    except (ValueError,AttributeError):detail='Local model rejected the request'
                    raise RuntimeError(str(detail)[:500])
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if 'error' in data:
                        raise RuntimeError(data['error'])
                    message = data.get('message', {})
                    text = message.get('content', '')
                    if text:
                        content += text
                        await on_token(text)
                    for position, call in enumerate(message.get('tool_calls', [])):
                        fn = call['function']
                        index = call.get('index', fn.get('index', position))
                        previous = calls.setdefault(index, {'type': 'function', 'function': {'name': '', 'arguments': {}}})['function']
                        if fn.get('name'):
                            previous['name'] = fn['name']
                        args = fn.get('arguments', {})
                        if isinstance(args, dict):
                            previous['arguments'].update(args)
                        else:
                            raise ValueError('Tool arguments must be an object')
                    if data.get('done'):
                        metrics = {key: data[key] for key in ('eval_count', 'eval_duration', 'load_duration', 'prompt_eval_count') if key in data}
        message = {'role': 'assistant', 'content': content}
        if calls:
            message['tool_calls'] = [calls[key] for key in sorted(calls)]
        return message, metrics
