"""
Контроллер для управления комбинированными сценариями AI -> SQL
"""
from typing import Dict, Any, Optional
from models.combo_scenario import ComboScenario, IterationResult
from controllers.sql_controller import SQLController


class ComboScenarioController:
    """Контроллер для выполнения комбинированных сценариев"""
    
    @staticmethod
    def create_scenario(main_task: str, iterations_count: int, iterative_task: str) -> ComboScenario:
        """Создает новый сценарий"""
        return ComboScenario(
            main_task=main_task,
            iterations_count=iterations_count,
            iterative_task=iterative_task
        )
    
    @staticmethod
    def execute_iteration(
        scenario: ComboScenario,
        iteration_number: int,
        ai_generate_func
    ) -> IterationResult:
        """
        Выполняет одну итерацию сценария
        
        Args:
            scenario: Сценарий для выполнения
            iteration_number: Номер итерации (начинается с 1)
            ai_generate_func: Функция для генерации SQL через AI
        
        Returns:
            IterationResult: Результат итерации
        """
        # Получаем промпт для текущей итерации
        prompt = scenario.get_prompt_for_iteration(iteration_number)
        
        result = IterationResult(
            iteration_number=iteration_number,
            prompt=prompt,
            ai_response="",
            sql_execution_result=None
        )
        
        try:
            # Шаг 1: Генерируем SQL через AI
            ai_result = ai_generate_func(prompt)
            if not ai_result.get('success'):
                result.error = f"AI generation failed: {ai_result.get('error', 'Unknown error')}"
                return result
            
            # Извлекаем SQL из ответа AI
            sql_code = ai_result.get('sql', '')
            if not sql_code:
                result.error = "AI не вернул SQL код"
                return result
            
            result.ai_response = sql_code
            
            # Шаг 2: Выполняем SQL
            sql_execution_result = SQLController.execute(sql_code)
            result.sql_execution_result = sql_execution_result
            
            if not sql_execution_result.get('success'):
                result.error = f"SQL execution failed: {sql_execution_result.get('error', 'Unknown error')}"
            
        except Exception as e:
            result.error = str(e)
        
        return result
    
    @staticmethod
    def execute_scenario(
        main_task: str,
        iterations_count: int,
        iterative_task: str,
        ai_generate_func,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Выполняет полный сценарий со всеми итерациями
        
        Args:
            main_task: Главное задание
            iterations_count: Количество итераций
            iterative_task: Итерационное задание
            ai_generate_func: Функция для генерации SQL через AI
            progress_callback: Функция обратного вызова для отслеживания прогресса
        
        Returns:
            Dict с результатом выполнения сценария
        """
        scenario = ComboScenarioController.create_scenario(
            main_task=main_task,
            iterations_count=iterations_count,
            iterative_task=iterative_task
        )
        
        scenario.status = "running"
        
        try:
            for i in range(1, iterations_count + 1):
                # Выполняем итерацию
                iteration_result = ComboScenarioController.execute_iteration(
                    scenario=scenario,
                    iteration_number=i,
                    ai_generate_func=ai_generate_func
                )
                
                # Добавляем результат в сценарий
                scenario.add_iteration_result(iteration_result)
                
                # Вызываем callback для обновления прогресса
                if progress_callback:
                    progress_callback({
                        'iteration': i,
                        'total': iterations_count,
                        'result': iteration_result.to_dict()
                    })
                
                # Если была ошибка, можно остановить выполнение или продолжить
                if iteration_result.error:
                    # Продолжаем выполнение даже при ошибках
                    pass
            
            scenario.status = "completed"
            
        except Exception as e:
            scenario.status = "error"
            scenario.error = str(e)
        
        return {
            'success': True,
            'scenario': scenario.to_dict()
        }
    
    @staticmethod
    def execute_single_iteration_step(
        main_task: str,
        iterations_count: int,
        iterative_task: str,
        current_iteration: int,
        previous_iterations: list,
        ai_generate_func
    ) -> Dict[str, Any]:
        """
        Выполняет один шаг итерации (для асинхронного выполнения)
        
        Args:
            main_task: Главное задание
            iterations_count: Общее количество итераций
            iterative_task: Итерационное задание
            current_iteration: Текущий номер итерации
            previous_iterations: Список результатов предыдущих итераций
            ai_generate_func: Функция для генерации SQL через AI
        
        Returns:
            Dict с результатом выполнения шага
        """
        # Восстанавливаем сценарий из предыдущих итераций
        scenario = ComboScenario(
            main_task=main_task,
            iterations_count=iterations_count,
            iterative_task=iterative_task
        )
        
        for it_data in previous_iterations:
            result = IterationResult(
                iteration_number=it_data['iteration_number'],
                prompt=it_data['prompt'],
                ai_response=it_data['ai_response'],
                sql_execution_result=it_data.get('sql_execution_result'),
                error=it_data.get('error'),
                timestamp=it_data.get('timestamp')
            )
            scenario.iterations.append(result)
        
        # Выполняем текущую итерацию (использует get_prompt_for_iteration)
        iteration_result = ComboScenarioController.execute_iteration(
            scenario=scenario,
            iteration_number=current_iteration,
            ai_generate_func=ai_generate_func
        )
        
        return {
            'success': True,
            'iteration_result': iteration_result.to_dict(),
            'is_completed': current_iteration >= iterations_count
        }

