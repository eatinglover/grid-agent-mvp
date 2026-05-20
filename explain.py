from src.utils import read_json, write_json
from src.ollama_client import ask_ollama
import json


def build_explain_prompt(result):
    return f"""
你是配电网电压治理专家。

请根据下面的快速决策结果，生成简洁的中文解释。
要求：
1. 不要长篇推理。
2. 说明电压异常情况。
3. 说明为什么选择这些设备。
4. 说明是否存在风险。
5. 控制在200字以内。

【快速决策结果】
{json.dumps(result, ensure_ascii=False, indent=2)}
"""


def main():
    results = read_json("output/fast_decision_results.json")
    explain_results = []

    for item in results:
        print("=" * 80)
        print(f"正在解释案例：{item['case_id']} - {item['area_name']}")

        prompt = build_explain_prompt(item)

        try:
            explanation = ask_ollama(prompt, model="qwen3:4b")
        except Exception as e:
            explanation = f"模型解释失败：{e}"

        item["llm_explanation"] = explanation
        explain_results.append(item)

        print(explanation[:500])

    write_json("output/explain_results.json", explain_results)
    print("=" * 80)
    print("解释结果已保存到 output/explain_results.json")


if __name__ == "__main__":
    main()