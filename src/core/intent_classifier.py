"""意图分类器：轻量级规则匹配"""
from typing import List, Dict


class IntentClassifier:
    """基于关键词的意图分类器，毫秒级响应，零 Token 成本"""

    def __init__(self):
        self.symptom_keywords = [
            "发热", "头痛", "恶寒", "汗出", "腹痛",
            "脉", "舌", "口渴", "呕", "咳", "寒", "热"
        ]
        self.follow_up_keywords = [
            "加减", "禁忌", "副作用", "剂量", "煎服", "注意"
        ]

    def classify(self, question: str, history: List[Dict]) -> str:
        """
        返回 'symptom_query' | 'follow_up' | 'out_of_scope'
        """
        has_symptom = any(kw in question for kw in self.symptom_keywords)
        has_followup = any(kw in question for kw in self.follow_up_keywords)

        # 无医学特征 + 无历史 → 越界
        if not has_symptom and not has_followup and len(history) == 0:
            return "out_of_scope"

        # 有历史 + 追问词 → 追问
        if len(history) > 0 and has_followup:
            return "follow_up"

        # 有症状词 → 症状查询
        if has_symptom:
            return "symptom_query"

        return "out_of_scope"


# 保留独立函数签名（兼容旧代码）
def classify_intent(question: str, history: List[Dict]) -> str:
    return IntentClassifier().classify(question, history)