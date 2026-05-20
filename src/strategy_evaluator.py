from typing import Dict, Any, List


def evaluate_action(action: Dict[str, Any]) -> Dict[str, Any]:
    """
    对单个治理动作进行评分。
    评分维度：
    1. effective_score：策略有效性
    2. economy_score：经济性
    3. feasibility_score：工程可落地性
    4. risk_score：风险评分，分数越高风险越低
    5. total_score：综合评分
    """

    device_type = action.get("device_type")
    action_type = action.get("action")

    effective_score = 60
    economy_score = 60
    feasibility_score = 60
    risk_score = 80

    # AVR / OLTC 调档
    if device_type in ["AVR", "OLTC"]:
        effective_score += 20
        economy_score += 20
        feasibility_score += 15

        if abs(action.get("adjust_step", 1)) >= 2:
            risk_score -= 10

        if device_type == "OLTC":
            risk_score -= 10

    # SVG 无功调节
    elif device_type == "SVG":
        effective_score += 25
        economy_score -= 10
        feasibility_score += 15
        risk_score += 5

    # 储能
    elif device_type == "ESS":
        effective_score += 20
        economy_score += 5
        feasibility_score += 10
        risk_score += 5

    # 光伏逆变器集群
    elif device_type == "PV_INVERTER_CLUSTER":
        if action_type == "inverter_absorb_reactive_power":
            effective_score += 25
            economy_score += 20
            feasibility_score += 15
            risk_score += 5

        elif action_type == "active_power_curtailment":
            effective_score += 20
            economy_score -= 30
            feasibility_score += 10
            risk_score -= 5

    # 分数限制在 0~100
    effective_score = max(0, min(100, effective_score))
    economy_score = max(0, min(100, economy_score))
    feasibility_score = max(0, min(100, feasibility_score))
    risk_score = max(0, min(100, risk_score))

    total_score = (
        effective_score * 0.4
        + economy_score * 0.25
        + feasibility_score * 0.25
        + risk_score * 0.1
    )

    evaluated_action = {
        **action,
        "evaluation": {
            "effective_score": effective_score,
            "economy_score": economy_score,
            "feasibility_score": feasibility_score,
            "risk_score": risk_score,
            "total_score": round(total_score, 2)
        }
    }

    return evaluated_action


def evaluate_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    对候选治理动作进行批量评分，并按综合评分从高到低排序。
    """

    evaluated = [evaluate_action(action) for action in actions]

    evaluated.sort(
        key=lambda x: x["evaluation"]["total_score"],
        reverse=True
    )

    return evaluated