from typing import List, Dict, Any, Optional
import json

def build_repair_context(
    bug_description: str,
    reproduction_evidence: List[Dict[str, Any]],
    diagnosis: Dict[str, Any],
    code_contexts: List[Dict[str, Any]],
    planner_strategy: Optional[Dict[str, Any]] = None,
    previous_attempts: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Constructs the prompt payload containing the repair context.
    """
    
    context_str = f"## BUG DESCRIPTION\n{bug_description}\n\n"
    
    if reproduction_evidence:
        context_str += "## REPRODUCTION EVIDENCE\n"
        for ev in reproduction_evidence:
            context_str += f"- {ev.get('type', 'Evidence')}"
            if 'file' in ev and ev['file']:
                context_str += f" in {ev['file']}"
            if 'line' in ev and ev['line']:
                context_str += f":{ev['line']}"
            context_str += f"\n  {ev.get('description', '')}\n"
        context_str += "\n"
        
    context_str += "## DIAGNOSIS\n"
    context_str += f"Root Cause: {diagnosis.get('root_cause', 'Unknown')}\n\n"
    context_str += f"Failure Mechanism: {diagnosis.get('failure_mechanism', 'Unknown')}\n\n"
    
    if diagnosis.get('affected_files'):
        context_str += "Affected Files: " + ", ".join(diagnosis['affected_files']) + "\n\n"
        
    if diagnosis.get('affected_functions'):
        context_str += "Affected Functions: " + ", ".join(diagnosis['affected_functions']) + "\n\n"
        
    if code_contexts:
        context_str += "## RELEVANT SOURCE CODE\n"
        for ctx in code_contexts:
            context_str += f"--- {ctx.get('file', 'Unknown')} (Lines {ctx.get('start_line', '?')}-{ctx.get('end_line', '?')}) ---\n"
            context_str += f"{ctx.get('content', '')}\n\n"

    if previous_attempts:
        context_str += "## PREVIOUS FAILED REPAIR ATTEMPTS\n"
        context_str += "IMPORTANT: The previous patches failed. Do NOT repeat them blindly.\n"
        for i, attempt in enumerate(previous_attempts, 1):
            context_str += f"--- ATTEMPT {i} ---\n"
            context_str += f"Strategy: {attempt.get('strategy', {}).get('strategy', 'N/A')}\n"
            context_str += f"Reviewer Feedback: {attempt.get('review', {}).get('reason', 'N/A')}\n"
            context_str += f"Patch Applied:\n```diff\n{attempt.get('patch', 'N/A')}\n```\n\n"
            
    if planner_strategy:
        context_str += "## NEW REPAIR STRATEGY\n"
        context_str += "Follow this strategy to generate the new patch.\n"
        context_str += f"Strategy: {planner_strategy.get('strategy', 'N/A')}\n"
        context_str += f"Reason: {planner_strategy.get('reason', 'N/A')}\n"
        context_str += f"Expected Change: {planner_strategy.get('expected_change', 'N/A')}\n\n"
            
    return context_str
