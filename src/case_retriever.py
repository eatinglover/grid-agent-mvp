from typing import Dict, Any, List


def match_real_cases(current_case: Dict[str, Any], case_library: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    简单案例匹配：
    根据电压异常类型 + 设备类型 + 关键词，匹配真实案例库。
    """
    voltage = current_case["voltage"]
    devices = current_case.get("devices", [])

    max_pu = voltage["max_pu"]
    min_pu = voltage["min_pu"]
    upper = voltage["upper_limit_pu"]
    lower = voltage["lower_limit_pu"]

    device_types = [d["device_type"] for d in devices]

    if max_pu > upper and min_pu < lower:
        abnormal_type = "two_way_voltage_violation"
    elif max_pu > upper:
        abnormal_type = "over_voltage"
    elif min_pu < lower:
        abnormal_type = "under_voltage"
    else:
        abnormal_type = "normal"

    matched = []

    for item in case_library:
        score = 0

        # 异常类型匹配
        if abnormal_type in item.get("abnormal_type", []):
            score += 5

        # 设备/措施匹配
        tags = item.get("strategy_tags", [])
        measures = item.get("devices_or_measures", [])

        if "AVR" in device_types and any("AVR" in t or "调压" in m for t in tags for m in measures):
            score += 3

        if "OLTC" in device_types and any("OLTC" in t or "有载调压" in m for t in tags for m in measures):
            score += 3

        if "ESS" in device_types and any("ESS" in t or "储能" in m for t in tags for m in measures):
            score += 3

        if "PV_INVERTER_CLUSTER" in device_types and any("inverter" in t or "逆变器" in m or "光伏集群" in m for t in tags for m in measures):
            score += 3

        # 光伏过剩特征
        if current_case.get("pv_power_kw", 0) > current_case.get("load_power_kw", 0):
            if "reverse_power_flow" in item.get("abnormal_type", []) or "pv_reverse_power" in item.get("abnormal_type", []):
                score += 2

        if score > 0:
            matched.append({
                "case_id": item["case_id"],
                "case_name": item["case_name"],
                "score": score,
                "summary": item["summary"],
                "strategy_tags": item.get("strategy_tags", [])
            })

    matched.sort(key=lambda x: x["score"], reverse=True)
    return matched[:3]