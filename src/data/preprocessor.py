import re
from zhconv import convert # 繁转简
from typing import Dict

valid_suffixes = ('湯', '散', '丸', '酒', '膏', '煎', '方', '飲', '洗方', '輩', '導')
special_allow = {'承氣輩', '五苓散加茵陳蒿'}  # 特殊保留

def clean_text(text: str) -> str:
    """去除标点、数字、英文字母，只保留中文字符（用于模型输入）"""
    return re.sub(r'[^\u4e00-\u9fff]', '', text)
    
def to_simplified(symptom: str) -> str:
    # 繁体转简体
    return convert(symptom, 'zh-cn')
    
def process_item(item: Dict) -> Dict:
    symptom = item['symptom'].strip()
    formula = item['formula'].strip()
    
    # 过滤太短症状
    if len(symptom) < 2:
        #print(f"{symptom}    {formula}")
        return None
        
    # 过滤非标准方剂名
    if not formula.endswith(valid_suffixes) and formula not in special_allow:
        #print(f"{symptom}    {formula}")
        return None
    
    return {
        'symptom': to_simplified(clean_text(symptom)),
        'formula': formula
    }