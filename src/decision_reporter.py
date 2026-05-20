from typing import Dict, Any


def build_decision_report(result: Dict[str, Any]) -> str:
    """
    将Agent结构化结果转成中文决策报告。
    """

    problem = result.get("problem_analysis", {})
    diagnosis = result.get("diagnosis", {})
    tool_plan = result.get("tool_plan", {})
    matched_cases = result.get("matched_real_cases", [])
    ranked_devices = result.get("ranked_devices", [])
    actions = result.get("checked_actions", [])
    warnings = result.get("warnings", [])

    lines = []

    lines.append("【电压治理智能体决策报告】")
    lines.append("")

    lines.append("一、异常诊断")
    lines.append(f"问题类型：{problem.get('problem_type', '未知')}")
    lines.append(f"诊断描述：{diagnosis.get('description', '无')}")
    lines.append(f"是否需要治理：{problem.get('need_control', False)}")
    lines.append("")

    lines.append("二、工具调用规划")
    lines.append(f"调度原因：{tool_plan.get('reason', '无')}")
    lines.append(f"是否检索案例库：{tool_plan.get('need_case_retrieval', False)}")
    lines.append(f"是否查询设备能力库：{tool_plan.get('need_device_capability', False)}")
    lines.append(f"是否生成治理策略：{tool_plan.get('need_strategy_generation', False)}")
    lines.append(f"是否进行安全校验：{tool_plan.get('need_safety_check', False)}")
    lines.append("")

    lines.append("三、历史案例参考")
    if matched_cases:
        for idx, case in enumerate(matched_cases, start=1):
            lines.append(
                f"{idx}. {case.get('case_name')}，匹配分数：{case.get('score')}，参考意义：{case.get('summary')}"
            )
    else:
        lines.append("未匹配到历史案例，或当前电压正常无需案例检索。")
    lines.append("")

    lines.append("四、设备能力评估")
    if ranked_devices:
        for idx, dev in enumerate(ranked_devices, start=1):
            lines.append(
                f"{idx}. {dev.get('device_name')}（{dev.get('device_type')}），"
                f"适配分数：{dev.get('score')}，能力：{', '.join(dev.get('capabilities', []))}。"
                f"规则说明：{dev.get('priority_rule')}"
            )
    else:
        lines.append("未进行设备能力排序，或当前无可用治理设备。")
    lines.append("")

    lines.append("五、最终治理动作")
    if actions:
        for idx, action in enumerate(actions, start=1):
            action_text = (
                f"{idx}. 设备 {action.get('device_id')}，类型 {action.get('device_type')}，"
                f"动作 {action.get('action')}，调节值 {action.get('value')} {action.get('unit')}"
            )

            if "before_tap" in action and "after_tap" in action:
                action_text += (
                    f"，当前档位：{action.get('before_tap')}，"
                    f"目标档位：{action.get('after_tap')}，"
                    f"调节步数：{action.get('adjust_step')} tap"
                )

            if "expected_effect" in action:
                effect = action.get("expected_effect", {})
                action_text += f"，预期效果：{effect.get('reason', '无')}"

                if "evaluation" in action:
                    eva = action.get("evaluation", {})
                    action_text += (
                        f"，综合评分：{eva.get('total_score')}，"
                        f"有效性：{eva.get('effective_score')}，"
                        f"经济性：{eva.get('economy_score')}，"
                        f"可落地性：{eva.get('feasibility_score')}，"
                        f"风险控制：{eva.get('risk_score')}"
                    )

            action_text += f"。原因：{action.get('reason', '无')}"

            lines.append(action_text)
    else:
        lines.append("当前无需执行治理动作。")
    lines.append("")

    lines.append("六、安全校验结果")
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("未发现越界、超容量或设备不可用等风险。")
    lines.append("")

    lines.append("七、结论")
    if actions:
        lines.append("智能体已根据电压异常状态、历史案例、设备能力和安全约束生成可执行治理策略。")
    else:
        lines.append("智能体判断当前无需治理或暂无可执行动作。")

    return "\n".join(lines)