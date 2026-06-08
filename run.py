#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ⚗️ DENIA PHARMACIST — ULTIMATE MEDICINAL CHEMISTRY RESEARCH BOT ⚗️          ║
║  Single-file, async, long-running, no-timeout pharmaceutical AI            ║
║  Model: mistral-medium-3.5-128b  |  Architecture: Deep Research Pipeline     ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage:
    pip install python-telegram-bot aiohttp
    export AI_API_KEY=sk-...
    export BOT_TOKEN=...
    python run.py

Or edit the CONFIG section below directly.
"""

import os
import sys
import re
import json
import uuid
import asyncio
import logging
from typing import Callable, Dict, Any
from dataclasses import dataclass, field

import aiohttp
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ═══════════════════════════════════════════════════════════════════════════════
# 1. CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.xah.io/v1/chat/completions")
AI_API_KEY = os.getenv("AI_API_KEY", "sk-e317a237354192e26f99951f06e4882779e8a0e08e86d2f71242e8ff770bdf24")
AI_MODEL = os.getenv("AI_MODEL", "mistral-medium-3.5-128b")
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "8192"))
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.3"))
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "300"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "8909561772:AAGQgxrbvXbi-RACF4_Z7iiS4R7NA6Za6wU")
BOT_NAME = os.getenv("BOT_NAME", "Denia Pharmacist")

MAX_RESEARCH_STEPS = int(os.getenv("MAX_RESEARCH_STEPS", "15"))
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "5"))

# ═══════════════════════════════════════════════════════════════════════════════
# 2. KNOWLEDGE BASE — EMBEDDED PHARMACEUTICAL CHEMISTRY
# ═══════════════════════════════════════════════════════════════════════════════

PHARMA_CHEMISTRY_CORE = """
## I. LỊCH SỬ HÓA HỌC & DƯỢC PHẨM (3000 TCN — Nay)

### 1. Thời kỳ Giả kim thuật & Dược thảo cổ đại (3000 TCN — 1500 SCN)
- **Ai Cập cổ đại**: Ebers Papyrus (1550 TCN) — 700+ công thức thuốc từ thực vật, khoáng vật, động vật.
- **Trung Quốc cổ đại**: Bản thảo cương mục (Li Shizhen, 1596) — 1892 vị thuốc. Nguyên tắc "Quân — Thần — Tá — Sứ".
- **Paracelsus (1493-1541)**: "Sola dosis facit venenum" — Chỉ liều lượng tạo nên chất độc. Chuyển từ giả kim sang iatrochemistry.
- **Cây coca & Cocaine**: Isolation by Niemann (1860); mở đầu kỷ nguyên alkaloid chemistry.
- **Digitalis purpurea**: Withering (1785) mô tả điều trị phù — bước ngoặt pharmacognosy.
- **Opium & Morphine**: Sertürner (1806) isolate morphine — first alkaloid isolated.
- **Quinine**: Isolation from Cinchona bark (1820) — foundation of antimalarial chemistry.

### 2. Hóa học Hiện đại & Cấu trúc phân tử (1800-1950)
- **Dalton (1803)**: Atomic theory — elements combine in fixed ratios.
- **Kekulé (1865)**: Cấu trúc benzene — nền tảng aromatic chemistry.
- **Fischer (1894)**: "Lock-and-key principle" — cơ sở molecular recognition.
- **Ehrlich (1909)**: Salvarsan (arsphenamine) — "magic bullet" đầu tiên, khởi đầu chemotherapy.
- **Domagk (1935)**: Prontosil (sulfonamide) — đột phá kháng sinh tổng hợp.
- **Fleming (1928)**: Penicillin — kháng sinh từ nấm mốc, mở đầu antibiotic era.
- **Woodward & Hoffmann (1965)**: Conservation of orbital symmetry — pericyclic reactions.
- **Pauling (1930s)**: Electronegativity, resonance, protein secondary structure (α-helix, β-sheet).
- **Watson & Crick (1953)**: DNA double helix — molecular biology foundation.
- **Hodgkin (1964)**: X-ray crystallography of penicillin, vitamin B12, insulin.

### 3. Kỷ nguyên Dược phẩm Phân tử (1950-2000)
- **Hansch & Fujita (1964)**: QSAR — định lượng mối liên hệ cấu trúc-hoạt tính.
- **Lipinski (1997)**: Rule of Five — MW ≤ 500, logP ≤ 5, HBD ≤ 5, HBA ≤ 10.
- **Kuntz et al. (1982)**: Docking algorithms — bắt đầu structure-based drug design (SBDD).
- **Combinatorial Chemistry (1990s)**: Tổng hợp song song hàng nghìn compound.
- **High-Throughput Screening (HTS)**: Tự động hóa assay hàng triệu compound.
- **Trost (1991)**: Atom economy — green chemistry principle.
- **Sharpless (2001)**: Click chemistry — Cu(I)-catalyzed azide-alkyne cycloaddition.

### 4. Kỷ nguyên Tính toán & Sinh học (2000-nay)
- **CADD**: Molecular docking, pharmacophore modeling, MD simulations (AMBER, GROMACS, NAMD).
- **DOS (Diversity-Oriented Synthesis)**: Tập trung đa dạng hóa scaffold.
- **Fragment-Based Drug Design (FBDD)**: Bắt đầu từ fragment nhỏ (MW < 300), tối ưu dần.
- **AI/ML trong Drug Discovery**: GNNs, VAE, GAN, Diffusion models.
- **AlphaFold (2020)**: Protein structure prediction — revolution cho SBDD.
- **PROTACs & Molecular Glues**: Protein degradation thay vì inhibition.
- **CRISPR & Chemical Biology**: Kết hợp gene editing với small molecule probes.
- **ADCs (Antibody-Drug Conjugates)**: Targeted delivery cytotoxic payload.
- **RNA therapeutics**: siRNA, mRNA vaccines (LNP delivery), ASO, aptamers.
- **Gene therapy**: AAV vectors, CRISPR-Cas9 editing.
- **Cell therapy**: CAR-T, CAR-NK, stem cells.

## II. NGUYÊN TẮC THIẾT KẾ THUỐC (Medicinal Chemistry Principles)

### 1. Structure-Activity Relationship (SAR)
- Bioisosteric replacement:
  - Classical: -OH ↔ -NH2, -O ↔ -S, -COOH ↔ -SO3H, -F ↔ -H, -Cl ↔ -CH3
  - Non-classical: Tetrazole ↔ Carboxylic acid, Oxadiazole ↔ Amide, Difluoromethylene ↔ Carbonyl
- Grimm's Hydride Displacement Law: Cấu trúc có cùng số electron valence thì tương đương.
- Topliss Tree: Decision tree for substituent optimization.
- Craig Plot: Visualizing σ (electronic) vs π (lipophilic) parameters.

### 2. Drug-Likeness & ADME
- **Lipinski Rule of 5**: MW ≤ 500, logP ≤ 5, HBD ≤ 5, HBA ≤ 10. Ngoại lệ: Natural products, antibiotics, CNS drugs.
- **Veber Rules**: Rotatable bonds ≤ 10, TPSA ≤ 140 Å².
- **Egan Egg**: logP vs TPSA plot để đánh giá hấp thu.
- **Pfizer 3/75 Rule**: cLogP < 3, TPSA > 75 → low permeability/high efflux risk.
- **Ghose Filter**: MW 160-480, logP -0.4-5.6, atom count 20-70.
- **ADME**:
  - Absorption: P-gp, BCRP, PEPT1, OATP transporters; pH-partition hypothesis.
  - Distribution: Vd, protein binding (albumin 60%, α1-acid glycoprotein).
  - Metabolism: Phase I (CYP450 — 1A2, 2D6, 3A4, 2C9, 2C19, 2B6, 2E1).
  - Phase II: Glucuronidation (UGT), Sulfation (SULT), Glutathione (GST), Acetylation (NAT), Methylation (COMT).
  - Excretion: Renal (GFR, tubular secretion/reabsorption), biliary, t1/2 = 0.693/k.
- **hERG channel**: IC50 > 30 μM để tránh QT prolongation (TdP risk).
- **AMES test**: Mutagenicity screening (Salmonella typhimurium strains).
- **BBB Penetration**: logP 1.5-3.0, MW < 400, TPSA < 90 Å², không phải P-gp substrate.
- **Caco-2 Permeability**: Papp > 8×10⁻⁶ cm/s = high permeability.
- **Solubility**: BCS Classification (Class I-IV based on solubility/permeability).

### 3. Thermodynamics of Binding
- ΔG_bind = -RT ln K_eq = ΔH_bind - TΔS_bind
- Enthalpy-driven: H-bonds, ionic interactions (specific, directional).
- Entropy-driven: Hydrophobic effect, release of ordered water molecules.
- "Magic methyl": Thêm methyl đúng vị trí tăng affinity 10-100x.
- Ligand Efficiency (LE) = ΔG_bind / N_non-H atoms. LE ≥ 0.3 kcal/mol/heavy atom.
- Lipophilic Ligand Efficiency (LLE) = pIC50 - cLogP. LLE ≥ 5-7 lý tưởng.
- Fit Quality (FQ) = LE / 0.3 (normalized).
- Binding Efficiency Index (BEI) = pIC50 / MW.
- Surface Efficiency Index (SEI) = pIC50 / PSA.

### 4. Pharmacophore & Molecular Recognition
- Pharmacophore: 3D arrangement của HBD, HBA, hydrophobic, aromatic, positive/negative ionizable features.
- Induced fit: Receptor thay đổi conformation khi bind ligand (Koshland, 1958).
- Conformational restriction: Rigid hóa phân tử giảm entropy penalty → tăng affinity.
- Prodrug strategy: Ester hóa tăng lipophilicity/permeability; cleavage by esterase.
- Hard drugs: Không bị metabolize; excreted unchanged (e.g., lithium, cisplatin).
- Soft drugs: Thiết kế để metabolize nhanh sau khi hoạt động (e.g., remifentanil).

### 5. Synthetic Accessibility & Retrosynthesis
- Corey & Cheng (1989): Logic of Chemical Synthesis — retrosynthetic analysis.
- Transform-based synthesis: C-C bond formation (Suzuki, Heck, Sonogashira, Grignard, Friedel-Crafts).
- Heterocycle synthesis: Pyridine, pyrimidine, imidazole, thiazole, oxazole synthesis.
- Green chemistry: Atom economy, E-factor, solvent selection (water, supercritical CO2, ionic liquids).
- Flow chemistry: Continuous processing, better heat/mass transfer.
- Photochemistry: Visible light catalysis, photocatalytic C-H activation.
- Biocatalysis: Enzyme-mediated synthesis, directed evolution of enzymes.

## III. HÓA HỌC PHÂN TÍCH & CẤU TRÚC

### 1. Phương pháp phân tích
- **NMR**: ¹H, ¹³C, ²H; 2D (COSY, HSQC, HMBC, NOESY, ROESY) — cấu trúc & stereochemistry.
- **Mass Spec**: ESI, MALDI, HRMS, MS/MS — xác định chính xác MW và formula.
- **X-ray Crystallography**: Độ phân giải nguyên tử, electron density maps, R-factor < 0.05.
- **Cryo-EM**: Cấu trúc protein ở trạng thái near-native, resolution < 2 Å.
- **CD Spectroscopy**: Secondary structure protein, chiral recognition.
- **IR/Raman**: Functional group identification, hydrogen bonding.
- **UV-Vis**: Chromophore analysis, concentration determination (Beer-Lambert law).
- **HPLC/GC**: Purity, chiral separation, metabolite profiling.
- **TLC**: Quick reaction monitoring.
- **DSC/TGA**: Thermal stability, polymorphism, melting point.

### 2. Tính chất Vật lý Hóa học
- pKa: Ionization state ảnh hưởng solubility, permeability, binding.
- LogP/LogD: Phân bố octanol/water ở pH khác nhau. LogD7.4 quan trọng cho physiological conditions.
- Solubility: Intrinsic vs kinetic; BCS classification (Class I-IV).
- Polymorphism: Different crystal forms → different bioavailability (Ritonavir scandal 1998).
- Salt selection: pH-solubility profile, counterion effects on stability.
- Co-crystals: Improving solubility without changing covalent structure.
- Amorphous solids: Higher energy state, better solubility but less stable.

## IV. DƯỢC LÝ HỌC (Pharmacology)

### 1. Pharmacokinetics (PK)
- Absorption: Fick's law, pH-partition hypothesis, transporters (PEPT1, OATP, OCT, MCT).
- Distribution: Vd = Dose/C₀; protein binding (albumin, α1-acid glycoprotein, lipoproteins).
- Blood-brain barrier: Tight junctions, P-gp efflux, passive diffusion, receptor-mediated transport.
- Metabolism: Phase I (CYP450, FMO, MAO, esterases), Phase II (UGT, SULT, GST, NAT, COMT).
- First-pass effect: Hepatic extraction ratio (E_h), bioavailability F = f_abs × (1 - E_h).
- Excretion: GFR, tubular secretion (OAT, OCT), reabsorption (passive, active).
- t½ = 0.693/k; k = CL/Vd; Steady-state: C_ss = (Dose/τ) / CL.
- AUC = F × Dose / CL; Clearance: CL = CL_renal + CL_hepatic + CL_other.
- Non-linear PK: Michaelis-Menten kinetics at high concentrations (phenytoin, ethanol).

### 2. Pharmacodynamics (PD)
- Receptor theory: Agonist, antagonist (competitive, non-competitive, uncompetitive, allosteric).
- Partial agonist: Efficacy < full agonist; Inverse agonist: negative constitutive activity.
- Signal transduction: GPCRs (7TM), RTKs, Ion channels, Nuclear receptors, Enzyme-linked.
- Second messengers: cAMP, cGMP, IP3, DAG, Ca²⁺, NO.
- Occupancy theory: Effect = (E_max × [D]) / (EC₅₀ + [D]).
- Schild analysis: pA₂ = -log[B] when dose-ratio = 2 (competitive antagonism).
- Allosteric modulation: Positive/negative modulator bind allosteric site.
- Spare receptors: EC₅₀ < K_d (not all receptors need to be occupied).
- Desensitization: Tachyphylaxis, tolerance, downregulation.
- Biomarkers: PD biomarkers, surrogate endpoints, clinical endpoints.

### 3. Toxicology & Safety Pharmacology
- LD₅₀/ED₅₀: Therapeutic Index (TI) = LD₅₀/ED₅₀.
- NOAEL: No Observed Adverse Effect Level → starting dose for FIH trials.
- Idiosyncratic toxicity: Reactive metabolites (quinones, nitrenium ions, acyl glucuronides, epoxides).
- hERG inhibition: IC₅₀ > 30 μM (CIPA guidelines); hERG IC₅₀ / C_max > 30-fold safety margin.
- CYP inhibition/induction: Drug-drug interactions (DDIs); [I]/K_i > 0.1 = weak inhibitor.
- Carcinogenicity: IARC classifications (Group 1-4), Ames test, micronucleus assay, 2-year rodent study.
- Hepatotoxicity: ALT/AST elevation, cholestasis (ALP, bilirubin), steatosis, DILI (Hy's law: ALT > 3×ULN + bilirubin > 2×ULN without obstruction = severe DILI risk).
- Nephrotoxicity: Creatinine clearance, BUN, tubular injury markers (KIM-1, NGAL).
- Cardiotoxicity: hERG, Nav1.5, Cav1.2; QT prolongation, arrhythmias.
- Genotoxicity: Ames, chromosomal aberration, mouse lymphoma assay, in vivo micronucleus.
- Reproductive toxicity: Segment I (fertility), II (teratogenicity), III (perinatal).
- Immunotoxicity: Cytokine storm, anaphylaxis, Stevens-Johnson syndrome.

## V. CÔNG NGHỆ HIỆN ĐẠI & AI

### 1. AI/ML trong Drug Discovery
- **Molecular Descriptors**: Morgan/ECFP, MACCS, topological, physicochemical, 3D pharmacophore.
- **Fingerprints**: ECFP4, FCFP4, MACCS keys, atom pairs, topological torsions.
- **Deep Learning**: GNNs (Graph Neural Networks) cho molecular property prediction.
- **Generative Models**: VAE, GAN, Diffusion models (de novo molecular design).
- **Reinforcement Learning**: Optimization of molecular properties with constraints.
- **AlphaFold**: Protein structure prediction — revolution cho SBDD.
- **Molecular Dynamics**: AMBER, GROMACS, NAMD — study protein-ligand interactions over time.
- **Free Energy Perturbation (FEP)**: Alchemical methods for binding affinity prediction.
- **MM-GBSA/PBSA**: End-state methods for scoring docking poses.
- **Virtual Screening**: Ligand-based (pharmacophore, similarity), structure-based (docking, MD).
- **ADMET Prediction**: QSPR models for solubility, permeability, metabolism, toxicity.
- **PK/PD Modeling**: Compartmental models, PBPK (Physiologically Based Pharmacokinetic).

### 2. Advanced Therapeutics
- **Biologics**: mAbs (IgG1, IgG2, IgG4), recombinant proteins, peptides, fusion proteins.
- **ADCs**: Antibody + linker + payload (MMAE, DM1, calicheamicin). DAR (Drug-to-Antibody Ratio).
- **Bispecific Antibodies**: Dual targeting (e.g., Blinatumomab: CD19×CD3).
- **RNA therapeutics**: siRNA (Dicer substrate), mRNA vaccines (LNP delivery), ASO, aptamers.
- **Gene therapy**: AAV serotypes, CRISPR-Cas9 (sgRNA design, PAM sequence), base editing, prime editing.
- **Cell therapy**: CAR-T (scFv-CD3ζ, 4-1BB/CD28 co-stimulation), CAR-NK, TCR-T, stem cells.
- **Oncolytic viruses**: Talimogene laherparepvec (T-VEC), adenovirus, HSV.
- **Microbiome therapeutics**: Fecal transplant, engineered probiotics, live biotherapeutics.

### 3. Formulation & Drug Delivery
- **Nanoparticles**: Liposomes (Doxil), polymeric micelles, solid lipid nanoparticles, polymeric nanoparticles.
- **Controlled release**: Osmotic pumps (OROS), matrix diffusion, reservoir systems, pulsatile release.
- **Transdermal**: Iontophoresis, microneedles, nanoemulsions.
- **Inhalation**: DPI, MDI, nebulizers; lung deposition (MMAD 1-5 μm).
- **Ocular**: Intravitreal, subconjunctival, nanoparticle delivery (BRB penetration).
- **Brain delivery**: Intranasal, BBB disruption (focused ultrasound), Trojan horse approaches.
- **Prodrugs**: Ester prodrugs, codrugs, antibody-directed enzyme prodrug therapy (ADEPT).
- **3D Printing**: Personalized dosing, complex geometries, multi-drug formulations.
- **Continuous Manufacturing**: Real-time release testing (RTRT), PAT (Process Analytical Technology).
"""

RESEARCH_METHODOLOGY = """
## VI. PHƯƠNG PHÁP NGHIÊN CỨU CHUYÊN SÂU (Deep Research Protocol)

Khi được yêu cầu nghiên cứu sâu, Denia Pharmacist thực hiện theo trình tự:

1. **Problem Decomposition**: Chia nhỏ vấn đề thành sub-questions có thể kiểm chứng.
2. **Literature Survey**: Tìm kiếm mechanism of action, SAR data, clinical evidence, known failures.
3. **Hypothesis Generation**: Đề xuất giả thuyết dựa trên structure-function relationship.
4. **Computational Analysis**: Áp dụng CADD principles, docking hypothesis, ADME prediction, FEP if applicable.
5. **Synthetic Planning**: Retrosynthetic analysis nếu là novel compound. Đánh giá atom economy, green chemistry.
6. **Safety Assessment**: Toxicity prediction, DDI screening, metabolite profiling, hERG risk, carcinogenicity.
7. **Iterative Refinement**: Self-correction dựa trên conflicting data. Ghi rõ confidence levels.
8. **Conclusion & Recommendation**: Tóm tắt evidence-based, ghi rõ uncertainty levels, suggest next experiments.

NGUYÊN TẮC BẮT BUỘC:
- LUÔN trích dẫn nguyên tắc khoa học, KHÔNG BỊA ĐẶT dữ liệu.
- Nếu không chắc chắn, ghi rõ "HYPOTHESIS" hoặc "REQUIRES EXPERIMENTAL VALIDATION".
- Phân biệt rõ "known fact" vs "prediction/model" vs "speculation".
- Cite specific rules (Lipinski, Veber, etc.) khi áp dụng.
- Nếu đề xuất novel compound, phải có retrosynthetic pathway khả thi.
"""

SYSTEM_PERSONA = """
Bạn là **Denia Pharmacist** — một nhà hóa học dược phẩm (Medicinal Chemist) và nhà nghiên cứu khoa học cấp cao.

Tính cách & Phong cách:
- Chính xác, khoa học, methodical. Không bao giờ bịa đặt dữ liệu.
- Sử dụng thuật ngữ chuyên ngành đúng ngữ cảnh (IUPAC, pharmacology, toxicology).
- Trình bày có cấu trúc: Hypothesis → Evidence → Analysis → Conclusion.
- Khi phân tích phân tử, luôn đề cập: functional groups, stereochemistry, physicochemical properties, potential metabolic sites.
- Khi đánh giá thuốc, luôn xem xét: Mechanism → PK/PD → Safety → Synthesis feasibility.
- Sử dụng ký hiệu hóa học chuẩn: δ (chemical shift), λ (wavelength), μ (micro), Å (Angstrom), ΔG, pKa, etc.
- Thiết kế đẹp: Dùng bảng, bullet points, headers rõ ràng, và phân cấp logic.
- Nếu là câu hỏi nghiên cứu dài, chia thành phases và báo cáo progress.
- Khi trả lời, luôn bắt đầu bằng tóm tắt ngắn (TL;DR) rồi chi tiết.

KIẾN THỨC NỀN: Bạn đã nắm vững toàn bộ lịch sử hóa học từ giả kim thuật, dược thảo cổ đại, đến CADD/AI hiện đại. Bạn hiểu sâu về SAR, ADME, QSAR, Lipinski, bioisosteres, pharmacophore, molecular recognition, thermodynamics of binding, CYP metabolism, toxicity prediction, và retrosynthetic analysis.

Bạn là một nhà hóa học thực thụ — không bao giờ đưa ra thông tin y tế mà không có cơ sở khoa học. Luôn khuyến cáo người dùng tham khảo ý kiến bác sĩ/dược sĩ cho quyết định lâm sàng.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# 3. AI CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class MistralClient:
    def __init__(self):
        self.base_url = AI_BASE_URL
        self.api_key = AI_API_KEY
        self.model = AI_MODEL
        self.max_tokens = AI_MAX_TOKENS
        self.temperature = AI_TEMPERATURE
        self.timeout = aiohttp.ClientTimeout(total=AI_TIMEOUT)

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
            async with session.post(self.base_url, headers=headers, json=payload) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"API Error {response.status}: {text}")
                data = await response.json()
                return data["choices"][0]["message"]["content"]

# ═══════════════════════════════════════════════════════════════════════════════
# 4. RESEARCH ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ResearchTask:
    task_id: str
    query: str
    mode: str
    max_steps: int = 15
    status: str = "pending"
    progress: int = 0
    result: str = ""
    steps_taken: list = field(default_factory=list)
    error: str = None

class ResearchEngine:
    def __init__(self):
        self.client = MistralClient()
        self.active_tasks: Dict[str, ResearchTask] = {}
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    async def execute_research(self, task: ResearchTask, progress_callback: Callable):
        async with self.semaphore:
            task.status = "working"
            try:
                # Step 1
                await progress_callback("🔬 <b>Phase 1/5</b>: Decomposing research problem...", 10)
                decomposition = await self.client.chat(
                    f"Decompose this pharmaceutical chemistry research question into 3-5 specific sub-problems. "
                    f"Return ONLY the sub-problems as a numbered list.\n\nQuery: {task.query}",
                    mode="research", temperature=0.2
                )
                task.steps_taken.append(("decomposition", decomposition))
                task.progress = 20

                # Step 2
                await progress_callback("📚 <b>Phase 2/5</b>: Synthesizing knowledge base...", 25)
                synthesis = await self.client.chat(
                    f"Based on these sub-problems, provide a comprehensive literature-style synthesis "
                    f"covering mechanisms, SAR data, and known clinical evidence. Be thorough.\n\n"
                    f"Sub-problems:\n{decomposition}\n\nOriginal query: {task.query}",
                    mode="research", temperature=0.2
                )
                task.steps_taken.append(("synthesis", synthesis))
                task.progress = 45

                # Step 3
                await progress_callback("🧮 <b>Phase 3/5</b>: Generating hypotheses & computational analysis...", 50)
                analysis = await self.client.chat(
                    f"Generate testable hypotheses and provide computational/pharmaceutical analysis "
                    f"including: ADME predictions, binding considerations, synthetic feasibility, and safety flags.\n\n"
                    f"Context from previous steps:\n{synthesis[:2000]}\n\n"
                    f"Original query: {task.query}",
                    mode="research", temperature=0.2
                )
                task.steps_taken.append(("analysis", analysis))
                task.progress = 70

                # Step 4
                await progress_callback("⚗️ <b>Phase 4/5</b>: Self-correction & cross-validation...", 75)
                validation = await self.client.chat(
                    f"Review the following analysis for scientific accuracy. Identify any conflicting data, "
                    f"logical errors, or overconfident claims. Correct them and assign confidence levels "
                    f"(High/Medium/Low) to each conclusion.\n\n{analysis[:3000]}",
                    mode="research", temperature=0.1
                )
                task.steps_taken.append(("validation", validation))
                task.progress = 90

                # Step 5
                await progress_callback("📊 <b>Phase 5/5</b>: Compiling final research report...", 95)
                final = await self.client.chat(
                    f"Compile a comprehensive, beautifully formatted research report from all phases. "
                    f"Include: Executive Summary, Background, Methodology, Key Findings, Hypotheses, "
                    f"Safety Considerations, Recommendations, and Uncertainty Declaration.\n\n"
                    f"Original Query: {task.query}\n\n"
                    f"Decomposition: {decomposition}\n\n"
                    f"Synthesis: {synthesis[:1500]}\n\n"
                    f"Analysis: {analysis[:1500]}\n\n"
                    f"Validation: {validation[:1500]}",
                    mode="research", temperature=0.3, max_tokens=8192
                )
                task.result = final
                task.progress = 100
                task.status = "completed"
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                raise

    def create_task(self, query: str, mode: str = "research") -> ResearchTask:
        task_id = str(uuid.uuid4())[:8]
        task = ResearchTask(task_id=task_id, query=query, mode=mode)
        self.active_tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> ResearchTask:
        return self.active_tasks.get(task_id)

engine = ResearchEngine()

# ═══════════════════════════════════════════════════════════════════════════════
# 5. UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def md_to_html(text: str) -> str:
    """Convert simple markdown to Telegram HTML"""
    # Escape HTML special chars first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    # Code
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    # Headers
    text = re.sub(r'^(#{1,3})\s+(.+)$', r'<b>\2</b>', text, flags=re.MULTILINE)
    # Bullet points
    text = re.sub(r'^-\s+', r'• ', text, flags=re.MULTILINE)
    return text

def truncate_text(text: str, max_length: int = 4000) -> str:
    if len(text) <= max_length:
        return text
    half = max_length // 2
    return text[:half] + "\n\n... [truncated] ...\n\n" + text[-half:]

# ═══════════════════════════════════════════════════════════════════════════════
# 6. TELEGRAM HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

client = MistralClient()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "⚗️ <b>Welcome to Denia Pharmacist</b> ⚗️\n\n"
        "🧪 <i>Your Advanced Medicinal Chemistry Research Companion</i>\n\n"
        "I am an AI research assistant specialized in:\n"
        "• 🧬 Drug Design & Discovery (CADD/SBDD/LBDD)\n"
        "• ⚛️ Molecular Analysis & SAR/QSAR\n"
        "• 🧫 ADME/Toxicity Prediction\n"
        "• 🔬 Retrosynthetic Planning\n"
        "• 📜 History of Chemistry & Pharmacognosy\n"
        "• 🧮 Reaction Balancing & Calculations\n\n"
        "<b>Commands:</b>\n"
        "/research &lt;query&gt; — Deep multi-step research (no timeout)\n"
        "/analyze &lt;molecule&gt; — Structural & physicochemical analysis\n"
        "/synthesize &lt;target&gt; — Retrosynthetic pathway design\n"
        "/adme &lt;compound&gt; — ADME & drug-likeness prediction\n"
        "/toxicity &lt;compound&gt; — Safety & toxicity assessment\n"
        "/history &lt;topic&gt; — Historical chemistry/pharmacy knowledge\n"
        "/formula &lt;equation&gt; — Balance chemical equations\n"
        "/status &lt;task_id&gt; — Check research progress\n"
        "/help — Show detailed capabilities\n\n"
        "🧪 <i>Model: mistral-medium-3.5-128b | Mode: Deep Research Enabled</i>"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.HTML)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 <b>Denia Pharmacist — Command Reference</b>\n\n"
        "🔬 <b>/research</b> &lt;query&gt;\n"
        "   Multi-phase deep research (15 steps max). No timeout.\n"
        "   Example: <code>/research Design a selective JAK2 inhibitor with improved hERG profile</code>\n\n"
        "⚛️ <b>/analyze</b> &lt;SMILES/name&gt;\n"
        "   Analyze molecular structure, functional groups, stereochemistry.\n"
        "   Example: <code>/analyze O=C(O)c1ccccc1O</code> (Salicylic acid)\n\n"
        "🧪 <b>/synthesize</b> &lt;target molecule&gt;\n"
        "   Propose retrosynthetic route with reagents & conditions.\n"
        "   Example: <code>/synthesize Aspirin from phenol</code>\n\n"
        "🧫 <b>/adme</b> &lt;compound&gt;\n"
        "   Predict absorption, distribution, metabolism, excretion.\n"
        "   Example: <code>/adme Ibuprofen</code>\n\n"
        "☠️ <b>/toxicity</b> &lt;compound&gt;\n"
        "   Evaluate acute/chronic toxicity, mutagenicity, hERG risk.\n"
        "   Example: <code>/toxicity Paracetamol overdose mechanism</code>\n\n"
        "📜 <b>/history</b> &lt;topic&gt;\n"
        "   Historical knowledge from alchemy to modern drug discovery.\n"
        "   Example: <code>/history Discovery of Penicillin</code>\n\n"
        "🧮 <b>/formula</b> &lt;chemical equation&gt;\n"
        "   Balance chemical reactions & calculate stoichiometry.\n"
        "   Example: <code>/formula C6H12O6 + O2 -&gt; CO2 + H2O</code>\n\n"
        "📊 <b>/status</b> &lt;task_id&gt;\n"
        "   Check progress of running research tasks.\n\n"
        "💬 <i>Direct message: Any chemistry question answered with full scientific rigor.</i>"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: <code>/analyze &lt;molecule name or SMILES&gt;</code>", parse_mode=ParseMode.HTML)
        return
    query = ' '.join(context.args)
    msg = await update.message.reply_text("⚛️ <b>Analyzing molecular structure...</b> 🔬", parse_mode=ParseMode.HTML)
    try:
        response = await client.chat(
            f"Perform a comprehensive medicinal chemistry analysis of: {query}\n\n"
            f"Include: 1) Structure & functional groups, 2) Physicochemical properties (predicted), "
            f"3) Potential biological targets, 4) Metabolic hot spots, 5) Drug-likeness assessment.",
            mode="analysis"
        )
        await msg.edit_text(truncate_text(md_to_html(response)), parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def synthesize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: <code>/synthesize &lt;target molecule&gt;</code>", parse_mode=ParseMode.HTML)
        return
    query = ' '.join(context.args)
    msg = await update.message.reply_text("🧪 <b>Planning retrosynthetic route...</b> ⚗️", parse_mode=ParseMode.HTML)
    try:
        response = await client.chat(
            f"Design a retrosynthetic analysis for: {query}\n\n"
            f"Provide: 1) Retrosynthetic disconnections, 2) Forward synthesis steps with reagents/conditions, "
            f"3) Yield estimates, 4) Green chemistry considerations, 5) Safety warnings for hazardous reagents.",
            mode="synthesis"
        )
        await msg.edit_text(truncate_text(md_to_html(response)), parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def adme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: <code>/adme &lt;compound name&gt;</code>", parse_mode=ParseMode.HTML)
        return
    query = ' '.join(context.args)
    msg = await update.message.reply_text("🧫 <b>Predicting ADME profile...</b> 📊", parse_mode=ParseMode.HTML)
    try:
        response = await client.chat(
            f"Provide a detailed ADME (Absorption, Distribution, Metabolism, Excretion) prediction for: {query}\n\n"
            f"Include: 1) Oral bioavailability (F%) estimate, 2) logP/logD, 3) Solubility class (BCS), "
            f"4) Major CYP enzymes involved, 5) Half-life estimate, 6) BBB penetration, 7) hERG risk, "
            f"8) Major transporters (P-gp, OATP, etc.).",
            mode="analysis"
        )
        await msg.edit_text(truncate_text(md_to_html(response)), parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def toxicity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: <code>/toxicity &lt;compound&gt;</code>", parse_mode=ParseMode.HTML)
        return
    query = ' '.join(context.args)
    msg = await update.message.reply_text("☠️ <b>Assessing toxicity profile...</b> 🧪", parse_mode=ParseMode.HTML)
    try:
        response = await client.chat(
            f"Conduct a comprehensive toxicity assessment for: {query}\n\n"
            f"Cover: 1) Acute toxicity (LD50 estimates), 2) Mechanism of toxicity, 3) Major target organs, "
            f"4) Carcinogenicity/mutagenicity (AMES prediction), 5) hERG IC50 prediction, 6) Hepatotoxicity (DILI risk), "
            f"7) Reactive metabolite formation, 8) Drug-drug interaction potential, 9) Teratogenicity/reproductive toxicity.",
            mode="toxicity"
        )
        await msg.edit_text(truncate_text(md_to_html(response)), parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: <code>/history &lt;topic&gt;</code>", parse_mode=ParseMode.HTML)
        return
    query = ' '.join(context.args)
    msg = await update.message.reply_text("📜 <b>Searching historical archives...</b> 🏛️", parse_mode=ParseMode.HTML)
    try:
        response = await client.chat(
            f"Provide a detailed historical account of: {query} in the context of chemistry and pharmacy.\n\n"
            f"Include: 1) Timeline of key discoveries, 2) Key figures and their contributions, "
            f"3) Evolution of thinking/paradigms, 4) Impact on modern science, 5) Interesting anecdotes or controversies.",
            mode="default"
        )
        await msg.edit_text(truncate_text(md_to_html(response)), parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def formula_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: <code>/formula &lt;chemical equation&gt;</code>", parse_mode=ParseMode.HTML)
        return
    query = ' '.join(context.args)
    msg = await update.message.reply_text("🧮 <b>Balancing chemical equation...</b> ⚖️", parse_mode=ParseMode.HTML)
    try:
        response = await client.chat(
            f"Balance this chemical equation and provide stoichiometric analysis: {query}\n\n"
            f"Show: 1) Balanced equation with coefficients, 2) Molar ratios, 3) Atom inventory (LHS vs RHS), "
            f"4) If organic, show mechanism type if applicable.",
            mode="default"
        )
        await msg.edit_text(truncate_text(md_to_html(response)), parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def research_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: <code>/research &lt;your deep research query&gt;</code>\n\n"
            "Example: <code>/research Design a brain-penetrant EGFR inhibitor for glioblastoma with minimal CYP3A4 metabolism</code>",
            parse_mode=ParseMode.HTML
        )
        return
    query = ' '.join(context.args)
    task = engine.create_task(query, mode="research")
    progress_msg = await update.message.reply_text(
        f"🔬 <b>Deep Research Initiated</b> 🔬\n\n"
        f"Task ID: <code>{task.task_id}</code>\n"
        f"Query: <i>{query[:100]}...</i>\n\n"
        f"⏳ Phase 0/5: Initializing... (0%)\n\n"
        f"ℹ️ This is a long-running task. Use <code>/status {task.task_id}</code> to check progress.",
        parse_mode=ParseMode.HTML
    )

    async def progress_callback(status_text: str, percent: int):
        try:
            await progress_msg.edit_text(
                f"🔬 <b>Deep Research in Progress</b> 🔬\n\n"
                f"Task ID: <code>{task.task_id}</code>\n"
                f"Query: <i>{query[:100]}...</i>\n\n"
                f"{status_text}\n"
                f"Progress: {percent}%\n\n"
                f"ℹ️ Use <code>/status {task.task_id}</code> for updates.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.warning(f"Progress update failed: {e}")

    asyncio.create_task(engine.execute_research(task, progress_callback))
    await asyncio.sleep(2)

    if task.status == "completed":
        await progress_msg.edit_text(
            f"✅ <b>Research Complete</b> ✅\n\n"
            f"Task ID: <code>{task.task_id}</code>\n\n"
            f"{truncate_text(md_to_html(task.result))}",
            parse_mode=ParseMode.HTML
        )
    elif task.status == "failed":
        await progress_msg.edit_text(f"❌ Research failed: {task.error}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: <code>/status &lt;task_id&gt;</code>", parse_mode=ParseMode.HTML)
        return
    task_id = context.args[0]
    task = engine.get_task(task_id)
    if not task:
        await update.message.reply_text(f"❌ Task <code>{task_id}</code> not found.", parse_mode=ParseMode.HTML)
        return
    if task.status == "completed":
        await update.message.reply_text(
            f"✅ <b>Task Completed</b> ✅\n\n"
            f"ID: <code>{task.task_id}</code>\n"
            f"Progress: 100%\n\n"
            f"{truncate_text(md_to_html(task.result))}",
            parse_mode=ParseMode.HTML
        )
    elif task.status == "failed":
        await update.message.reply_text(
            f"❌ <b>Task Failed</b> ❌\n\n"
            f"ID: <code>{task.task_id}</code>\n"
            f"Error: {task.error}",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            f"⏳ <b>Task Running</b> ⏳\n\n"
            f"ID: <code>{task.task_id}</code>\n"
            f"Status: {task.status}\n"
            f"Progress: {task.progress}%\n"
            f"Steps completed: {len(task.steps_taken)}/5\n\n"
            f"Last update: {task.steps_taken[-1][0] if task.steps_taken else 'Initializing...'}",
            parse_mode=ParseMode.HTML
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    deep_keywords = ['research', 'nghiên cứu', 'study', 'investigate', 'design', 'synthesize', 'thorough', 'deep', 'chi tiết', 'phân tích sâu']
    is_deep = any(k in text.lower() for k in deep_keywords) or len(text) > 200

    if is_deep:
        task = engine.create_task(text, mode="research")
        msg = await update.message.reply_text(
            f"🔬 <b>Auto-Detected Deep Query</b> 🔬\n\n"
            f"Task ID: <code>{task.task_id}</code>\n"
            f"Starting comprehensive analysis...\n\n"
            f"ℹ️ Check status with <code>/status {task.task_id}</code>",
            parse_mode=ParseMode.HTML
        )

        async def cb(status, pct):
            try:
                if pct % 20 == 0:
                    await msg.edit_text(
                        f"🔬 <b>Researching...</b> {pct}%\n\n"
                        f"Task: <code>{task.task_id}</code>\n"
                        f"{status}",
                        parse_mode=ParseMode.HTML
                    )
            except:
                pass

        asyncio.create_task(engine.execute_research(task, cb))

        for _ in range(150):
            await asyncio.sleep(2)
            if task.status in ["completed", "failed"]:
                break

        if task.status == "completed":
            await msg.edit_text(
                f"✅ <b>Analysis Complete</b> ✅\n\n"
                f"{truncate_text(md_to_html(task.result))}",
                parse_mode=ParseMode.HTML
            )
        elif task.status == "failed":
            await msg.edit_text(f"❌ Error: {task.error}")
        else:
            await msg.edit_text(
                f"⏳ <b>Still Researching...</b> ⏳\n\n"
                f"Task ID: <code>{task.task_id}</code>\n"
                f"Current progress: {task.progress}%\n"
                f"Check later with <code>/status {task.task_id}</code>",
                parse_mode=ParseMode.HTML
            )
    else:
        msg = await update.message.reply_text("🧪 <i>Analyzing...</i>", parse_mode=ParseMode.HTML)
        try:
            response = await client.chat(text, mode="default")
            await msg.edit_text(truncate_text(md_to_html(response)), parse_mode=ParseMode.HTML)
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ An error occurred. Please try again or use /help for assistance."
        )

# ═══════════════════════════════════════════════════════════════════════════════
# 7. MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )
    logger = logging.getLogger(__name__)

    if not AI_API_KEY or not BOT_TOKEN:
        logger.error("❌ Missing AI_API_KEY or BOT_TOKEN. Set them as environment variables or edit the CONFIG section in run.py")
        sys.exit(1)

    logger.info("🔬 Initializing Denia Pharmacist...")
    logger.info("⚗️ Loading pharmaceutical chemistry knowledge base...")
    logger.info("🧪 Calibrating AI client (mistral-medium-3.5-128b)...")
    logger.info("📡 Connecting to Telegram API...")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("synthesize", synthesize_command))
    application.add_handler(CommandHandler("adme", adme_command))
    application.add_handler(CommandHandler("toxicity", toxicity_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("formula", formula_command))
    application.add_handler(CommandHandler("research", research_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("✅ All systems nominal. Denia Pharmacist is online.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
