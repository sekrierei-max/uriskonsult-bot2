import re
from typing import Union


def parse_channel_id(channel_id: str) -> Union[int, str]:
    """
    Универсальный парсер ID канала.
    
    Поддерживает:
    - Числовые ID с -100 (Telegram) -> возвращает int
    - Обычные числа -> возвращает int  
    - Username с @ -> возвращает str
    - Username без @ -> добавляет @ и возвращает str
    """
    if not channel_id:
        raise ValueError("CHANNEL_ID не может быть пустым")
    
    channel_id = channel_id.strip()
    
    # Случай 1: Числовой ID (включая отрицательные)
    if re.match(r'^-?\d+$', channel_id):
        return int(channel_id)
    
    # Случай 2: Username (с @ или без)
    if not channel_id.startswith('@'):
        channel_id = f'@{channel_id}'
    
    return channel_id


def is_numeric_channel_id(channel_id: Union[int, str]) -> bool:
    """Проверяет, является ли ID канала числовым."""
    if isinstance(channel_id, int):
        return True
    if isinstance(channel_id, str) and re.match(r'^-?\d+$', channel_id.strip()):
        return True
    return False