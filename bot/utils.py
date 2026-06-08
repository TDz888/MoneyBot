import re
from typing import Optional

def format_molecular_formula(formula: str) -> str:
    """Format molecular formula with subscripts"""
    def subscript(match):
        return ''.join(f'_{c}' for c in match.group(1))
    return re.sub(r'(\d+)', lambda m: ''.join([f'₍{c}₎' for c in m.group(1)]), formula)

def escape_markdown(text: str) -> str:
    """Escape Telegram markdown characters"""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

def truncate_middle(text: str, max_length: int = 4000) -> str:
    """Truncate long text for Telegram with ellipsis in middle"""
    if len(text) <= max_length:
        return text
    half = max_length // 2
    return text[:half] + "\n\n... [truncated] ...\n\n" + text[-half:]

def calculate_drug_likeness(mw: float, logp: float, hbd: int, hba: int) -> dict:
    """Calculate Lipinski violations and drug-likeness score"""
    violations = 0
    details = []
    
    if mw > 500:
        violations += 1
        details.append(f"MW = {mw} (>500)")
    if logp > 5:
        violations += 1
        details.append(f"LogP = {logp} (>5)")
    if hbd > 5:
        violations += 1
        details.append(f"HBD = {hbd} (>5)")
    if hba > 10:
        violations += 1
        details.append(f"HBA = {hba} (>10)")
    
    # Veber rules
    rotatable = 0  # Would need actual calculation
    tpsa = 0       # Would need actual calculation
    
    status = "Excellent" if violations == 0 else "Good" if violations == 1 else "Poor"
    
    return {
        "violations": violations,
        "status": status,
        "details": details,
        "lipinski_pass": violations <= 1
    }

def format_research_report(text: str) -> str:
    """Add chemistry-themed formatting to research reports"""
    # Add section headers styling
    text = re.sub(r'^(#{1,3})\s+(.+)$', r'🔬 *\2*', text, flags=re.MULTILINE)
    # Highlight chemical terms
    text = re.sub(r'\b(CYP\d+[A-Z]\d*|hERG|ADME|SAR|QSAR|IC50|EC50|Ki|Kd|pKa|logP|MW|TPSA)\b', r'`\1`', text)
    return text
