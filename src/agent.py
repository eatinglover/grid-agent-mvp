from typing import Dict, Any

from src.rule_engine import generate_rule_based_strategy, safety_check
from src.case_retriever import match_real_cases
from src.device_capability import get_device_capabilities, rank_devices_for_problem
from src.strategy_evaluator import evaluate_actions
from src.strategy_conflict_resolver import resolve_strategy_conflicts

class VoltageGovernanceAgent:

    def __init__(self, case_library, capability_library):
        self.case_library = case_library
        self.capability_library = capability_library

    def analyze_voltage_problem(self, case: Dict[str, Any]) -> Dict[str, Any]:
        voltage = case["voltage"]

        max_pu = voltage["max_pu"]
        min_pu = voltage["min_pu"]
        upper = voltage["upper_limit_pu"]
        lower = voltage["lower_limit_pu"]

        if max_pu > upper and min_pu < lower:
            return {
                "problem_type": "two_way_voltage_violation",
                "need_control": True,
                "description": "同时存在过电压与欠电压"
            }

        if max_pu > upper:
            return {
                "problem_type": "over_voltage",
                "need_control": True,
                "description": "存在过电压"
            }

        if min_pu < lower:
            return {
                "problem_type": "under_voltage",
                "need_control": True,
                "description": "存在欠电压"
            }

        return {
            "problem_type": "normal",
            "need_control": False,
            "description": "电压正常，无需治理"
        }

    def plan_tools(self, problem: Dict[str, Any]) -> Dict[str, Any]:
        """
        工具调度规划：
        根据问题类型决定调用哪些工具。
        """

        if not problem["need_control"]:
            return {
                "need_case_retrieval": False,
                "need_device_capability": False,
                "need_strategy_generation": False,
                "need_safety_check": False,
                "reason": "电压正常，无需调用治理工具。"
            }

        if problem["problem_type"] in ["over_voltage", "under_voltage"]:
            return {
                "need_case_retrieval": True,
                "need_device_capability": True,
                "need_strategy_generation": True,
                "need_safety_check": True,
                "reason": "存在单向电压越限，需要检索案例、查询设备能力、生成策略并进行安全校验。"
            }

        if problem["problem_type"] == "two_way_voltage_violation":
            return {
                "need_case_retrieval": True,
                "need_device_capability": True,
                "need_strategy_generation": True,
                "need_safety_check": True,
                "reason": "存在双向越限，需要综合历史案例和设备能力进行治理。"
            }

        return {
            "need_case_retrieval": False,
            "need_device_capability": False,
            "need_strategy_generation": False,
            "need_safety_check": False,
            "reason": "未识别到需要治理的问题。"
        }

    def run(self, case: Dict[str, Any]) -> Dict[str, Any]:

        print("\n[Agent] 开始分析台区...")

        # =====================================================
        # 1. 问题分析
        # =====================================================

        problem = self.analyze_voltage_problem(case)

        print(f"[Agent] 检测到问题类型：{problem['problem_type']}")
        print(f"[Agent] 是否需要治理：{problem['need_control']}")

        # =====================================================
        # 2. 工具调度规划
        # =====================================================

        tool_plan = self.plan_tools(problem)

        print(f"[Agent] 工具调度计划：{tool_plan}")

        matched_cases = []

        device_capabilities = []

        ranked_devices = []

        checked_strategy = {
            "diagnosis": {
                "status": "normal",
                "severity": "none",
                "exceed_value_pu": 0,
                "description": "电压处于正常范围"
            },
            "checked_actions": [],
            "warnings": []
        }

        # =====================================================
        # 3. 历史案例检索
        # =====================================================

        if tool_plan["need_case_retrieval"]:

            print("[Agent] 正在检索历史案例...")

            matched_cases = match_real_cases(
                case,
                self.case_library
            )

            print(f"[Agent] 匹配到 {len(matched_cases)} 个案例")

        # =====================================================
        # 4. 设备能力分析
        # =====================================================

        if tool_plan["need_device_capability"]:

            print("[Agent] 正在查询设备能力库...")

            device_capabilities = get_device_capabilities(
                case,
                self.capability_library
            )

            ranked_devices = rank_devices_for_problem(
                problem["problem_type"],
                device_capabilities
            )

            print(f"[Agent] 设备优先级排序：{ranked_devices}")

        # =====================================================
        # 5. 候选策略生成
        # =====================================================

        if tool_plan["need_strategy_generation"]:

            print("[Agent] 正在生成候选策略...")

            strategy = generate_rule_based_strategy(case)

        else:

            strategy = {
                "diagnosis": checked_strategy["diagnosis"],
                "candidate_actions": [],
                "rule_reason": "电压正常，无需生成治理策略。"
            }

        # =====================================================
        # 6. 安全校验
        # =====================================================

        if tool_plan["need_safety_check"]:

            print("[Agent] 正在进行安全校验...")

            checked_strategy = safety_check(
                strategy,
                case
            )

        # =====================================================
        # 7. 策略综合评分
        # =====================================================

        if checked_strategy["checked_actions"]:

            print("[Agent] 正在进行策略综合评分...")

            checked_strategy["checked_actions"] = evaluate_actions(
            checked_strategy["checked_actions"]
        )

        print("[Agent] 正在进行策略冲突消解...")

        checked_strategy["checked_actions"] = resolve_strategy_conflicts(
            checked_strategy["checked_actions"]
        )

        # =====================================================
        # 8. 汇总输出
        # =====================================================

        final_result = {

            "problem_analysis": problem,

            "tool_plan": tool_plan,

            "matched_real_cases": matched_cases,

            "device_capabilities": device_capabilities,

            "ranked_devices": ranked_devices,

            "diagnosis": checked_strategy["diagnosis"],

            "checked_actions": checked_strategy["checked_actions"],

            "warnings": checked_strategy["warnings"],

            "agent_mode": "VoltageGovernanceAgent_v4_multi_agent"
        }

        print("[Agent] 决策完成")

        return final_result