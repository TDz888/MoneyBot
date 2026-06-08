import asyncio
from typing import Callable, List, Dict, Any
from ai_client import MistralClient

class ResearchTask:
    def __init__(self, task_id: str, query: str, mode: str, max_steps: int = 15):
        self.task_id = task_id
        self.query = query
        self.mode = mode
        self.max_steps = max_steps
        self.status = "pending"  # pending, working, completed, failed
        self.progress = 0
        self.result = ""
        self.steps_taken = []
        self.error = None
    
    def to_dict(self):
        return {
            "task_id": self.task_id,
            "status": self.status,
            "progress": self.progress,
            "steps": len(self.steps_taken),
            "error": self.error
        }

class ResearchEngine:
    def __init__(self):
        self.client = MistralClient()
        self.active_tasks: Dict[str, ResearchTask] = {}
        self.semaphore = asyncio.Semaphore(5)  # Max concurrent deep researches
    
    async def execute_research(self, task: ResearchTask, progress_callback: Callable[[str, int], Any]):
        """Execute multi-step research with progress tracking"""
        async with self.semaphore:
            task.status = "working"
            
            try:
                # Step 1: Problem Decomposition
                await progress_callback("🔬 **Phase 1/5**: Decomposing research problem...", 10)
                decomposition = await self.client.chat(
                    f"Decompose this pharmaceutical chemistry research question into 3-5 specific sub-problems. "
                    f"Return ONLY the sub-problems as a numbered list.\n\nQuery: {task.query}",
                    mode="research",
                    temperature=0.2
                )
                task.steps_taken.append(("decomposition", decomposition))
                task.progress = 20
                
                # Step 2: Literature/Knowledge Synthesis
                await progress_callback("📚 **Phase 2/5**: Synthesizing knowledge base...", 25)
                synthesis = await self.client.chat(
                    f"Based on these sub-problems, provide a comprehensive literature-style synthesis "
                    f"covering mechanisms, SAR data, and known clinical evidence. Be thorough.\n\n"
                    f"Sub-problems:\n{decomposition}\n\nOriginal query: {task.query}",
                    mode="research",
                    temperature=0.2
                )
                task.steps_taken.append(("synthesis", synthesis))
                task.progress = 45
                
                # Step 3: Hypothesis & Analysis
                await progress_callback("🧮 **Phase 3/5**: Generating hypotheses & computational analysis...", 50)
                analysis = await self.client.chat(
                    f"Generate testable hypotheses and provide computational/pharmaceutical analysis "
                    f"including: ADME predictions, binding considerations, synthetic feasibility, and safety flags.\n\n"
                    f"Context from previous steps:\n{synthesis[:2000]}\n\n"
                    f"Original query: {task.query}",
                    mode="research",
                    temperature=0.2
                )
                task.steps_taken.append(("analysis", analysis))
                task.progress = 70
                
                # Step 4: Self-Correction & Validation
                await progress_callback("⚗️ **Phase 4/5**: Self-correction & cross-validation...", 75)
                validation = await self.client.chat(
                    f"Review the following analysis for scientific accuracy. Identify any conflicting data, "
                    f"logical errors, or overconfident claims. Correct them and assign confidence levels "
                    f"(High/Medium/Low) to each conclusion.\n\n{analysis[:3000]}",
                    mode="research",
                    temperature=0.1
                )
                task.steps_taken.append(("validation", validation))
                task.progress = 90
                
                # Step 5: Final Report
                await progress_callback("📊 **Phase 5/5**: Compiling final research report...", 95)
                final = await self.client.chat(
                    f"Compile a comprehensive, beautifully formatted research report from all phases. "
                    f"Include: Executive Summary, Background, Methodology, Key Findings, Hypotheses, "
                    f"Safety Considerations, Recommendations, and Uncertainty Declaration.\n\n"
                    f"Original Query: {task.query}\n\n"
                    f"Decomposition: {decomposition}\n\n"
                    f"Synthesis: {synthesis[:1500]}\n\n"
                    f"Analysis: {analysis[:1500]}\n\n"
                    f"Validation: {validation[:1500]}",
                    mode="research",
                    temperature=0.3,
                    max_tokens=8192
                )
                
                task.result = final
                task.progress = 100
                task.status = "completed"
                
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                raise
    
    def create_task(self, query: str, mode: str = "research") -> ResearchTask:
        import uuid
        task_id = str(uuid.uuid4())[:8]
        task = ResearchTask(task_id, query, mode)
        self.active_tasks[task_id] = task
        return task
    
    def get_task(self, task_id: str) -> ResearchTask:
        return self.active_tasks.get(task_id)
    
    async def run_task(self, task: ResearchTask, callback: Callable):
        asyncio.create_task(self.execute_research(task, callback))
