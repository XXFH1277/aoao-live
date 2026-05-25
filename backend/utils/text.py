from __future__ import annotations


def tokenize(text: str) -> list[str]:
    normalized = text.lower()
    tokens = [
        token
        for token in normalized.replace("/", " ").replace("，", " ").replace("？", " ").split()
        if token
    ]
    chinese_terms = [
        "舟山", "海鲜", "礼盒", "送礼", "家庭", "家里", "聚餐", "过节",
        "节日", "长辈", "发货", "保存", "规格", "文旅", "普陀山", "朱家尖",
        "东极岛", "民宿", "船班", "天气", "价格", "库存", "退款", "售后",
    ]
    tokens.extend(term for term in chinese_terms if term in text)
    return tokens
