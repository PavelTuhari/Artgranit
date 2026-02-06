"""
Модель для управления комбинированными сценариями AI -> SQL
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class IterationResult:
    """Результат одной итерации"""
    iteration_number: int
    prompt: str  # Запрос к AI
    ai_response: str  # Ответ AI (SQL)
    sql_execution_result: Optional[Dict[str, Any]] = None  # Результат выполнения SQL
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует результат итерации в словарь"""
        return {
            'iteration_number': self.iteration_number,
            'prompt': self.prompt,
            'ai_response': self.ai_response,
            'sql_execution_result': self.sql_execution_result,
            'error': self.error,
            'timestamp': self.timestamp
        }


@dataclass
class ComboScenario:
    """Модель комбинированного сценария"""
    main_task: str  # Главная тема/задание
    iterations_count: int  # Количество итераций
    iterative_task: str  # Итерационное задание
    iterations: List[IterationResult] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, error
    current_iteration: int = 0
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_iteration_result(self, result: IterationResult):
        """Добавляет результат итерации"""
        self.iterations.append(result)
        self.current_iteration = len(self.iterations)
    
    def get_prompt_for_iteration(self, iteration_number: int) -> str:
        """Возвращает промпт для указанной итерации"""
        if iteration_number == 1:
            # Первая итерация - возвращаем главное задание
            return self.main_task
        
        # Для последующих итераций используем результат AI из ПЕРВОЙ итерации
        if not self.iterations or len(self.iterations) == 0:
            return self.main_task
        
        first_iteration = self.iterations[0]  # Берем результат ПЕРВОЙ итерации
        
        # Формируем промпт на основе результата ПЕРВОЙ итерации
        prompt_parts = []
        
        # Добавляем результат AI из первой итерации (структура таблицы) без префикса
        if first_iteration.ai_response:
            prompt_parts.append(first_iteration.ai_response)
        
        # Добавляем номер текущей итерации
        prompt_parts.append(f"Текущая итерация: {iteration_number}")
        
        # Добавляем итерационное задание
        prompt_parts.append(f"Итерационное задание: {self.iterative_task}")
        
        combined_prompt = "\n\n".join(prompt_parts)
        return combined_prompt
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует сценарий в словарь"""
        return {
            'main_task': self.main_task,
            'iterations_count': self.iterations_count,
            'iterative_task': self.iterative_task,
            'iterations': [it.to_dict() for it in self.iterations],
            'status': self.status,
            'current_iteration': self.current_iteration,
            'error': self.error,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComboScenario':
        """Создает сценарий из словаря"""
        scenario = cls(
            main_task=data['main_task'],
            iterations_count=data['iterations_count'],
            iterative_task=data['iterative_task'],
            status=data.get('status', 'pending'),
            current_iteration=data.get('current_iteration', 0),
            error=data.get('error'),
            created_at=data.get('created_at', datetime.now().isoformat())
        )
        # Восстанавливаем итерации
        for it_data in data.get('iterations', []):
            result = IterationResult(
                iteration_number=it_data['iteration_number'],
                prompt=it_data['prompt'],
                ai_response=it_data['ai_response'],
                sql_execution_result=it_data.get('sql_execution_result'),
                error=it_data.get('error'),
                timestamp=it_data.get('timestamp', datetime.now().isoformat())
            )
            scenario.iterations.append(result)
        return scenario

