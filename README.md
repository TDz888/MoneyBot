<p align="center">
  <img src="https://imagetourl.cloud/s7lu81lk.jpg" width="200" style="border-radius: 50%; box-shadow: 0 8px 32px rgba(139, 92, 246, 0.3);">
</p>

<h1 align="center">⚗️ Denia Pharmacist</h1>
<p align="center">
  <em>Your chill research buddy for Medicinal Chemistry & Drug Discovery</em><br>
  <sub>🧪 Built for long nights in the lab. No timeouts. No stress. 🌙</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white">
  <img src="https://img.shields.io/badge/AI-Mistral--3.5-FF6B6B?style=for-the-badge">
  <img src="https://img.shields.io/badge/Async-%E2%9A%A1-brightgreen?style=for-the-badge">
</p>

---

## 🌿 What's this?

**Denia Pharmacist** is a Telegram bot that lives and breathes medicinal chemistry. Whether you're pulling an all-nighter trying to design a kinase inhibitor, or just curious why aspirin works, this bot has your back.

It runs **deep research pipelines** with no timeout limits — ask it to design a brain-penetrant JAK2 inhibitor, and it'll spend 5 phases thinking it through while you grab coffee. ☕

> *"Sola dosis facit venenum — Only the dose makes the poison."*  
> — Paracelsus, probably while vibing to lo-fi

---

## 🧬 What it knows

The bot comes with a **fat embedded knowledge base** covering:

| Era | Vibe | Highlights |
|-----|------|------------|
| 🏺 **Ancient** | Ebers Papyrus, Li Shizhen, Paracelsus | 700+ formulas, "Quân-Thần-Tá-Sứ" |
| ⚗️ **Classical** | Kekulé, Fischer, Ehrlich, Fleming | Benzene, Lock-and-key, Salvarsan, Penicillin |
| 🧪 **Modern** | Hansch, Lipinski, Woodward | QSAR, Rule of Five, Atom economy |
| 🤖 **Future** | AlphaFold, AI/ML, PROTACs, CRISPR | GNNs, Diffusion models, Gene editing |

So yeah, it basically knows chemistry from *3000 BCE to 2026*.

---

## 🚀 Quick Start

### 1. Install stuff
```bash
pip install python-telegram-bot aiohttp
```

### 2. Set your keys
```bash
export AI_API_KEY="sk-your-key-here"
export BOT_TOKEN="your-bot-token-from-@BotFather"
```

> 💡 Pro tip: Or just edit the `CONFIG` section in `run.py` directly if you're lazy (no judgment).

### 3. Run it
```bash
python run.py
```

You'll see something like:
```
🔬 Initializing Denia Pharmacist...
⚗️ Loading pharmaceutical chemistry knowledge base...
🧪 Calibrating AI client...
📡 Connecting to Telegram API...
✅ All systems nominal. Denia Pharmacist is online.
```

Done. Go message your bot. 📱

---

## 📋 Commands

| Command | What it does | Example |
|---------|--------------|---------|
| `/start` | Say hi 👋 | — |
| `/help` | Show the full menu | — |
| `/research` | 🔬 Deep dive (5 phases, no timeout) | `/research Design a CNS-penetrant EGFR inhibitor` |
| `/analyze` | ⚛️ Break down a molecule | `/analyze O=C(O)c1ccccc1O` |
| `/synthesize` | 🧪 Plan your synthesis | `/synthesize Aspirin from phenol` |
| `/adme` | 🧫 Predict ADME profile | `/adme Ibuprofen` |
| `/toxicity` | ☠️ Safety check | `/toxicity Paracetamol overdose` |
| `/history` | 📜 Chemistry history lesson | `/history Discovery of Penicillin` |
| `/formula` | 🧮 Balance equations | `/formula C6H12O6 + O2 -> CO2 + H2O` |
| `/status` | ⏳ Check your research task | `/status abc12345` |

### 🧠 Auto-Mode

Just send a normal message:
- **Short & sweet** → Quick scientific answer
- **Long or complex** → Bot auto-detects and launches a **deep research task** with a task ID you can track

---

## 🔬 How Deep Research Works

When you hit `/research`, the bot goes through a whole pipeline:

```
Phase 1 🔍  Decompose the problem
Phase 2 📚  Synthesize knowledge (SAR, mechanisms, clinical data)
Phase 3 🧮  Generate hypotheses + computational analysis
Phase 4 ⚗️  Self-correct & validate (no cap, it checks itself)
Phase 5 📊  Compile a beautiful final report
```

All async. All chill. You can check `/status` anytime while it thinks.

---

## ⚙️ Config (Optional Tweaks)

| Variable | Default | What it does |
|----------|---------|--------------|
| `AI_BASE_URL` | `https://api.xah.io/v1/chat/completions` | API endpoint |
| `AI_MODEL` | `mistral-medium-3.5-128b` | The brain |
| `AI_MAX_TOKENS` | `8192` | How much it can write |
| `AI_TEMPERATURE` | `0.3` | Creativity (0.0 = robot, 1.0 = poet) |
| `AI_TIMEOUT` | `300` | API timeout (seconds) |
| `MAX_RESEARCH_STEPS` | `15` | Max depth for research |
| `MAX_CONCURRENT_TASKS` | `5` | How many tasks at once |

---

## 🎯 Use Cases

- **MedChem students** studying for exams at 2 AM
- **PhD candidates** brainstorming retrosynthetic routes
- **Pharma researchers** doing quick ADME sanity checks
- **Curious minds** wondering *"why does this drug work?"*
- **Anyone** who wants to balance a redox reaction without crying

---

## ⚠️ Real Talk (Disclaimer)

- 🏥 **This is NOT a doctor.** Always consult actual medical professionals for clinical decisions.
- 🔬 **It doesn't make up data**, but double-check anything mission-critical.
- 🔑 **Don't leak your API keys.** Use `.env` files, not GitHub.
- ☕ **It works best with coffee.** (That's on you though.)

---

## 🌙 Vibe Check

<p align="center">
  <img src="https://imagetourl.cloud/s7lu81lk.jpg" width="100" style="border-radius: 50%;">
  <br><br>
  <em>"Precision in every molecule. Science in every answer."</em><br>
  <sub>— Denia Pharmacist, probably listening to synthwave while docking ligands</sub>
</p>

---

<p align="center">
  Made with 🧪, ⚛️, and way too much caffeine.<br>
  <sub>Pull requests welcome. Lab accidents not.</sub>
</p>
