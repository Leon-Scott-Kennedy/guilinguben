"""数据加载与持久化"""
import json
from typing import List, Tuple
from src.data.preprocessor import process_item

class DataLoader:
    def __init__(self, data_path: str):
        self.data_path = data_path
    
    """加载数据、清洗、去重、编码，返回 (texts, labels)"""
    def load(self) -> Tuple[List[str], List[str]]:
        with open(self.data_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        
        # 清洗
        cleaned = [res for res in (process_item(item) for item in raw) if res is not None]
        
        # 去重
        seen = set()
        unique = []
        for item in cleaned:
            if item['symptom'] not in seen:
                seen.add(item['symptom'])
                unique.append(item)
        
        texts = [item['symptom'] for item in unique]
        labels = [item['formula'] for item in unique]
        return texts, labels