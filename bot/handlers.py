from telegram import Update
from telegram.ext import ContextTypes
from ai_client import MistralClient
from research_engine import ResearchEngine
from utils import truncate_middle, format_research_report, escape_markdown
import asyncio
import logging

logger = logging.getLogger(__name__)

client = MistralClient()
engine = ResearchEngine()

# ==================== COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "⚗️ **Welcome to Denia Pharmacist** ⚗️\n\n"
        "🧪 *Your Advanced Medicinal Chemistry Research Companion*\n\n"
        "I am an AI research assistant specialized in:\n"
        "• 🧬 Drug Design & Discovery (CADD/SBDD/LBDD)\n"
        "• ⚛️ Molecular Analysis & SAR/QSAR\n"
        "• 🧫 ADME/Toxicity Prediction\n"
        "• 🔬 Retrosynthetic Planning\n"
        "• 📜 History of Chemistry & Pharmacognosy\n"
        "• 🧮 Reaction Balancing & Calculations\n\n"
        "*Commands:*\n"
        "/research `<query>` — Deep multi-step research (no timeout)\n"
        "/analyze `<molecule>` — Structural & physicochemical analysis\n"
        "/synthesize `<target>` — Retrosynthetic pathway design\n"
        "/adme `<compound>` — ADME & drug-likeness prediction\n"
        "/toxicity `<compound>` — Safety & toxicity assessment\n"
        "/history `<topic>` — Historical chemistry/pharmacy knowledge\n"
        "/formula `<equation>` — Balance chemical equations\n"
        "/status `<task_id>` — Check research progress\n"
        "/help — Show detailed capabilities\n\n"
        "🧪 *Model*: `mistral-medium-3.5-128b` | *Mode*: Deep Research Enabled"
    )
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **Denia Pharmacist — Command Reference**\n\n"
        "🔬 */research* `<query>`\n"
        "   Multi-phase deep research (15 steps max). No timeout.\n"
        "   Example: `/research Design a selective JAK2 inhibitor with improved hERG profile`\n\n"
        "⚛️ */analyze* `<SMILES/name>`\n"
        "   Analyze molecular structure, functional groups, stereochemistry.\n"
        "   Example: `/analyze O=C(O)c1ccccc1O` (Salicylic acid)\n\n"
        "🧪 */synthesize* `<target molecule>`\n"
        "   Propose retrosynthetic route with reagents & conditions.\n"
        "   Example: `/synthesize Aspirin from phenol`\n\n"
        "🧫 */adme* `<compound>`\n"
        "   Predict absorption, distribution, metabolism, excretion.\n"
        "   Example: `/adme Ibuprofen`\n\n"
        "☠️ */toxicity* `<compound>`\n"
        "   Evaluate acute/chronic toxicity, mutagenicity, hERG risk.\n"
        "   Example: `/toxicity Paracetamol overdose mechanism`\n\n"
        "📜 */history* `<topic>`\n"
        "   Historical knowledge from alchemy to modern drug discovery.\n"
        "   Example: `/history Discovery of Penicillin`\n\n"
        "🧮 */formula* `<chemical equation>`\n"
        "   Balance chemical reactions & calculate stoichiometry.\n"
        "   Example: `/formula C6H12O6 + O2 -> CO2 + H2O`\n\n"
        "📊 */status* `<task_id>`\n"
        "   Check progress of running research tasks.\n\n"
        "💬 *Direct message*: Any chemistry question answered with full scientific rigor."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/analyze <molecule name or SMILES>`", parse_mode='Markdown')
        return
    
    query = ' '.join(context.args)
    msg = await update.message.reply_text("⚛️ **Analyzing molecular structure...** 🔬", parse_mode='Markdown')
    
    try:
        response = await client.chat(
            f"Perform a comprehensive medicinal chemistry analysis of: {query}\n\n"
            f"Include: 1) Structure & functional groups, 2) Physicochemical properties (predicted), "
            f"3) Potential biological targets, 4) Metabolic hot spots, 5) Drug-likeness assessment.",
            mode="analysis"
        )
        await msg.edit_text(truncate_middle(response), parse_mode='Markdown')
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def synthesize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/synthesize <target molecule>`", parse_mode='Markdown')
        return
    
    query = ' '.join(context.args)
    msg = await update.message.reply_text("🧪 **Planning retrosynthetic route...** ⚗️", parse_mode='Markdown')
    
    try:
        response = await client.chat(
            f"Design a retrosynthetic analysis for: {query}\n\n"
            f"Provide: 1) Retrosynthetic disconnections, 2) Forward synthesis steps with reagents/conditions, "
            f"3) Yield estimates, 4) Green chemistry considerations, 5) Safety warnings for hazardous reagents.",
            mode="synthesis"
        )
        await msg.edit_text(truncate_middle(response), parse_mode='Markdown')
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def adme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/adme <compound name>`", parse_mode='Markdown')
        return
    
    query = ' '.join(context.args)
    msg = await update.message.reply_text("🧫 **Predicting ADME profile...** 📊", parse_mode='Markdown')
    
    try:
        response = await client.chat(
            f"Provide a detailed ADME (Absorption, Distribution, Metabolism, Excretion) prediction for: {query}\n\n"
            f"Include: 1) Oral bioavailability (F%) estimate, 2) logP/logD, 3) Solubility class (BCS), "
            f"4) Major CYP enzymes involved, 5) Half-life estimate, 6) BBB penetration, 7) hERG risk, "
            f"8) Major transporters (P-gp, OATP, etc.).",
            mode="analysis"
        )
        await msg.edit_text(truncate_middle(response), parse_mode='Markdown')
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def toxicity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/toxicity <compound>`", parse_mode='Markdown')
        return
    
    query = ' '.join(context.args)
    msg = await update.message.reply_text("☠️ **Assessing toxicity profile...** 🧪", parse_mode='Markdown')
    
    try:
        response = await client.chat(
            f"Conduct a comprehensive toxicity assessment for: {query}\n\n"
            f"Cover: 1) Acute toxicity (LD50 estimates), 2) Mechanism of toxicity, 3) Major target organs, "
            f"4) Carcinogenicity/mutagenicity (AMES prediction), 5) hERG IC50 prediction, 6) Hepatotoxicity (DILI risk), "
            f"7) Reactive metabolite formation, 8) Drug-drug interaction potential, 9) Teratogenicity/reproductive toxicity.",
            mode="toxicity"
        )
        await msg.edit_text(truncate_middle(response), parse_mode='Markdown')
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/history <topic>`", parse_mode='Markdown')
        return
    
    query = ' '.join(context.args)
    msg = await update.message.reply_text("📜 **Searching historical archives...** 🏛️", parse_mode='Markdown')
    
    try:
        response = await client.chat(
            f"Provide a detailed historical account of: {query} in the context of chemistry and pharmacy.\n\n"
            f"Include: 1) Timeline of key discoveries, 2) Key figures and their contributions, "
            f"3) Evolution of thinking/paradigms, 4) Impact on modern science, 5) Interesting anecdotes or controversies.",
            mode="default"
        )
        await msg.edit_text(truncate_middle(response), parse_mode='Markdown')
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def formula_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/formula <chemical equation>`", parse_mode='Markdown')
        return
    
    query = ' '.join(context.args)
    msg = await update.message.reply_text("🧮 **Balancing chemical equation...** ⚖️", parse_mode='Markdown')
    
    try:
        response = await client.chat(
            f"Balance this chemical equation and provide stoichiometric analysis: {query}\n\n"
            f"Show: 1) Balanced equation with coefficients, 2) Molar ratios, 3) Atom inventory (LHS vs RHS), "
            f"4) If organic, show mechanism type if applicable.",
            mode="default"
        )
        await msg.edit_text(truncate_middle(response), parse_mode='Markdown')
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def research_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: `/research <your deep research query>`\n\n"
            "Example: `/research Design a brain-penetrant EGFR inhibitor for glioblastoma with minimal CYP3A4 metabolism`",
            parse_mode='Markdown'
        )
        return
    
    query = ' '.join(context.args)
    task = engine.create_task(query, mode="research")
    
    # Send initial message with task ID
    progress_msg = await update.message.reply_text(
        f"🔬 **Deep Research Initiated** 🔬\n\n"
        f"Task ID: `{task.task_id}`\n"
        f"Query: _{query[:100]}..._\n\n"
        f"⏳ Phase 0/5: Initializing... (0%)\n\n"
        f"ℹ️ This is a long-running task. Use `/status {task.task_id}` to check progress.",
        parse_mode='Markdown'
    )
    
    async def progress_callback(status_text: str, percent: int):
        try:
            await progress_msg.edit_text(
                f"🔬 **Deep Research in Progress** 🔬\n\n"
                f"Task ID: `{task.task_id}`\n"
                f"Query: _{query[:100]}..._\n\n"
                f"{status_text}\n"
                f"Progress: {percent}%\n\n"
                f"ℹ️ Use `/status {task.task_id}` for updates.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Progress update failed: {e}")
    
    # Start background research
    asyncio.create_task(engine.execute_research(task, progress_callback))
    
    # Wait a bit then show final result if quick, otherwise let user poll
    await asyncio.sleep(2)
    
    if task.status == "completed":
        await progress_msg.edit_text(
            f"✅ **Research Complete** ✅\n\n"
            f"Task ID: `{task.task_id}`\n\n"
            f"{truncate_middle(task.result)}",
            parse_mode='Markdown'
        )
    elif task.status == "failed":
        await progress_msg.edit_text(f"❌ Research failed: {task.error}")
    # else: still running, message already shows progress

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/status <task_id>`", parse_mode='Markdown')
        return
    
    task_id = context.args[0]
    task = engine.get_task(task_id)
    
    if not task:
        await update.message.reply_text(f"❌ Task `{task_id}` not found.", parse_mode='Markdown')
        return
    
    if task.status == "completed":
        await update.message.reply_text(
            f"✅ **Task Completed** ✅\n\n"
            f"ID: `{task.task_id}`\n"
            f"Progress: 100%\n\n"
            f"{truncate_middle(task.result)}",
            parse_mode='Markdown'
        )
    elif task.status == "failed":
        await update.message.reply_text(
            f"❌ **Task Failed** ❌\n\n"
            f"ID: `{task.task_id}`\n"
            f"Error: {task.error}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"⏳ **Task Running** ⏳\n\n"
            f"ID: `{task.task_id}`\n"
            f"Status: {task.status}\n"
            f"Progress: {task.progress}%\n"
            f"Steps completed: {len(task.steps_taken)}/5\n\n"
            f"Last update: {task.steps_taken[-1][0] if task.steps_taken else 'Initializing...'}",
            parse_mode='Markdown'
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct text messages"""
    text = update.message.text
    
    # Quick heuristic: if message is very long or contains "research", "study", "investigate", trigger deep mode
    deep_keywords = ['research', 'nghiên cứu', 'study', 'investigate', 'design', 'synthesize', 'thorough', 'deep', 'chi tiết']
    is_deep = any(k in text.lower() for k in deep_keywords) or len(text) > 200
    
    if is_deep:
        # Route to research command logic
        task = engine.create_task(text, mode="research")
        msg = await update.message.reply_text(
            f"🔬 **Auto-Detected Deep Query** 🔬\n\n"
            f"Task ID: `{task.task_id}`\n"
            f"Starting comprehensive analysis...\n\n"
            f"ℹ️ Check status with `/status {task.task_id}`",
            parse_mode='Markdown'
        )
        
        async def cb(status, pct):
            try:
                if pct % 20 == 0:
                    await msg.edit_text(
                        f"🔬 **Researching...** {pct}%\n\n"
                        f"Task: `{task.task_id}`\n"
                        f"{status}",
                        parse_mode='Markdown'
                    )
            except:
                pass
        
        asyncio.create_task(engine.execute_research(task, cb))
        
        # Wait for completion
        for _ in range(150):  # Poll for up to ~5 minutes (2s * 150)
            await asyncio.sleep(2)
            if task.status in ["completed", "failed"]:
                break
        
        if task.status == "completed":
            await msg.edit_text(
                f"✅ **Analysis Complete** ✅\n\n"
                f"{truncate_middle(task.result)}",
                parse_mode='Markdown'
            )
        elif task.status == "failed":
            await msg.edit_text(f"❌ Error: {task.error}")
        else:
            await msg.edit_text(
                f"⏳ **Still Researching...** ⏳\n\n"
                f"Task ID: `{task.task_id}`\n"
                f"Current progress: {task.progress}%\n"
                f"Check later with `/status {task.task_id}`",
                parse_mode='Markdown'
            )
    else:
        # Quick response
        msg = await update.message.reply_text("🧪 *Analyzing...*", parse_mode='Markdown')
        try:
            response = await client.chat(text, mode="default")
            await msg.edit_text(truncate_middle(response), parse_mode='Markdown')
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")
