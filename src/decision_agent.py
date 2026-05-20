import json
from typing import Dict, Any
from src.ollama_client import ask_ollama


def build_prompt(case: Dict[str, Any], checked_strategy: Dict[str, Any]) -> str:
    return f"""
你是一个配电网光伏台区电压治理智能体。
你的任务是根据台区数据、规则引擎候选策略和安全校验结果，输出最终治理建议。

重要要求：
1. 不允许调用台区不存在的设备。
2. 不允许超过设备容量或档位范围。
3. 如果电压过高，优先考虑SVG吸收无功、储能充电、调压器/OLTC降档。
4. 如果电压过低，优先考虑SVG注入无功、储能放电、调压器/OLTC升档。
5. OLTC/调压器不宜频繁动作。
6. 输出必须包含：电压诊断、推荐动作、原因、风险提示。
7. 不要编造不存在的数据。
8. 请尽量输出JSON格式，不要输出Markdown。

【台区实时数据】
{json.dumps(case, ensure_ascii=False, indent=2)}

【规则引擎与安全校验结果】
{json.dumps(checked_strategy, ensure_ascii=False, indent=2)}

请输出最终电压治理决策。
"""


def llm_decision(case: Dict[str, Any], checked_strategy: Dict[str, Any], model: str = "qwen3:4b") -> Dict[str, Any]:
    prompt = build_prompt(case, checked_strategy)
    response = ask_ollama(prompt, model=model)
    return {
        "llm_raw_response": response
    }
