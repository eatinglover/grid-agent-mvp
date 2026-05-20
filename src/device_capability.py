from typing import Dict, Any, List


def get_device_capabilities(
    case: Dict[str, Any],
    capability_library: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    根据当前台区已有设备，查询设备能力库。
    """
    devices = case.get("devices", [])
    device_types = [d["device_type"] for d in devices]

    matched = []

    for item in capability_library:
        if item["device_type"] in device_types:
            matched.append(item)

    return matched


def score_device_for_problem(
    problem_type: str,
    device_capability: Dict[str, Any]
) -> Dict[str, Any]:
    """
    根据异常类型，对设备适配度进行简单评分。
    """
    score = 0

    if problem_type in device_capability.get("suitable_for", []):
        score += 5

    response_speed = device_capability.get("response_speed")

    if response_speed == "fast":
        score += 3
    elif response_speed == "medium":
        score += 2
    elif response_speed == "slow":
        score += 1

    score += device_capability.get("economic_score", 0) * 0.2
    score += device_capability.get("engineering_feasibility_score", 0) * 0.2

    return {
        "device_type": device_capability["device_type"],
        "device_name": device_capability["device_name"],
        "score": round(score, 2),
        "capabilities": device_capability.get("capabilities", []),
        "priority_rule": device_capability.get("priority_rule", "")
    }


def rank_devices_for_problem(
    problem_type: str,
    device_capabilities: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    对当前台区可用设备进行排序。
    """
    ranked = [
        score_device_for_problem(problem_type, item)
        for item in device_capabilities
    ]

    ranked.sort(key=lambda x: x["score"], reverse=True)

    return ranked