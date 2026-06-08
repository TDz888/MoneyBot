import aiohttp
import json
import asyncio
from config import Config
from knowledge_base import PHARMA_CHEMISTRY_CORE, RESEARCH_METHODOLOGY, SYSTEM_PERSONA

class MistralClient:
    def __init__(self):
        self.base_url = Config.AI_BASE_URL
        self.api_key = Config.AI_API_KEY
        self.model = Config.AI_MODEL
        self.max_tokens = Config.AI_MAX_TOKENS
        self.temperature = Config.AI_TEMPERATURE
        self.timeout = aiohttp.ClientTimeout(total=Config.AI_TIMEOUT)
    
    def _build_system_prompt(self, mode="default"):
        base = SYSTEM_PERSONA + "\n\n" + PHARMA_CHEMISTRY_CORE
        
        if mode == "research":
            base += "\n\n" + RESEARCH_METHODOLOGY
            base += "\n\nBạn đang ở chế độ NGHIÊN CỨU SÂU. Hãy phân tích từng bước, chi tiết, và tự đánh giá lại kết quả của mình."
        elif mode == "synthesis":
            base += "\n\nBạn đang ở chế độ TỔNG HỢP HÓA HỌC. Hãy đề xuất retrosynthetic pathway, chọn reagents phù hợp, đánh giá yield và green chemistry principles."
        elif mode == "analysis":
            base += "\n\nBạn đang ở chế độ PHÂN TÍCH PHÂN TỬ. Hãy phân tích cấu trúc, tính chất vật lý, hóa học, và dự đoán hành vi sinh học."
        elif mode == "toxicity":
            base += "\n\nBạn đang ở chế độ ĐÁNH GIÁ ĐỘC TÍNH. Hãy đánh giá: acute toxicity, chronic effects, carcinogenicity, teratogenicity, hERG inhibition, CYP interactions, và metabolite toxicity."
        
        return base
    
    async def chat(self, user_message: str, mode="default", temperature=None, max_tokens=None):
        temp = temperature or self.temperature
        tokens = max_tokens or self.max_tokens
        
        system_prompt = self._build_system_prompt(mode)
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": temp,
            "max_tokens": tokens,
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                self.base_url,
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"API Error {response.status}: {text}")
                
                data = await response.json()
                return data["choices"][0]["message"]["content"]
    
    async def chat_stream(self, user_message: str, mode="default"):
        """Streaming for long responses - yields chunks"""
        system_prompt = self._build_system_prompt(mode)
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                self.base_url,
                headers=headers,
                json=payload
            ) as response:
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str == '[DONE]':
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except:
                            continue
