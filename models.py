from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Article:
    id: Optional[int]
    full_text: str
    teaser_id: Optional[int]
    reminder_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    def __post_init__(self):
        if self.full_text and len(self.full_text) < 10:
            raise ValueError("Текст статьи слишком короткий")
    
    @property
    def teaser(self) -> str:
        if self.full_text:
            return self.full_text[:500] + "..."
        return ""

@dataclass
class ScheduledPost:
    id: Optional[int]
    content: str
    scheduled_time: datetime
    status: str
    article_id: Optional[int]
    post_type: str
    fail_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    retry_count: int = 0
    
    def __post_init__(self):
        valid_statuses = ['pending', 'published', 'failed', 'cancelled']
        if self.status not in valid_statuses:
            raise ValueError(f"Статус должен быть одним из: {valid_statuses}")
        
        valid_types = ['teaser', 'reminder', 'standalone']
        if self.post_type not in valid_types:
            raise ValueError(f"Тип поста должен быть одним из: {valid_types}")
    
    @property
    def is_published(self) -> bool:
        return self.status == 'published'
    
    @property
    def is_failed(self) -> bool:
        return self.status == 'failed'
    
    @property
    def can_retry(self) -> bool:
        return self.status == 'failed' and self.retry_count < 3