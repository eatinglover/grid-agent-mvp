from typing import List, Dict, Any


def resolve_strategy_conflicts(
    actions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    """
    策略冲突消解：
    1. 同设备仅保留最高评分动作
    2. 光伏逆变器优先无功控制
    3. 总动作数量限制
    """

    if not actions:
        return []

    # =====================================================
    # 1. 按设备分组
    # =====================================================

    grouped = {}

    for action in actions:

        device_id = action["device_id"]

        if device_id not in grouped:
            grouped[device_id] = []

        grouped[device_id].append(action)

    resolved = []

    # =====================================================
    # 2. 每个设备只保留最高分动作
    # =====================================================

    for device_id, device_actions in grouped.items():

        # 光伏逆变器特殊规则：
        # 优先Q/V无功控制
        inverter_qv = [
            a for a in device_actions
            if a["action"] == "inverter_absorb_reactive_power"
        ]

        if inverter_qv:
            resolved.append(inverter_qv[0])
            continue

        # 按综合评分排序
        device_actions.sort(
            key=lambda x: x.get(
                "evaluation",
                {}
            ).get(
                "total_score",
                0
            ),
            reverse=True
        )

        resolved.append(device_actions[0])

    # =====================================================
    # 3. 全局排序
    # =====================================================

    resolved.sort(
        key=lambda x: x.get(
            "evaluation",
            {}
        ).get(
            "total_score",
            0
        ),
        reverse=True
    )

    # =====================================================
    # 4. 限制最大动作数量
    # =====================================================

    MAX_ACTIONS = 3

    resolved = resolved[:MAX_ACTIONS]

    return resolved