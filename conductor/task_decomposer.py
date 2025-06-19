#!/usr/bin/env python3
"""
動的タスク分解機能 - クエリ複雑度に基づく自動的なサブタスク生成
"""

import re
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from .agent import Task

logger = logging.getLogger(__name__)

class TaskComplexity(Enum):
    """タスクの複雑度レベル"""
    SIMPLE = "simple"      # 単一の明確なアクション
    MODERATE = "moderate"  # 2-3のステップが必要
    COMPLEX = "complex"    # 複数の独立したコンポーネント
    VERY_COMPLEX = "very_complex"  # 大規模な並列処理が必要

@dataclass
class ComplexityAnalysis:
    """複雑度分析の結果"""
    complexity: TaskComplexity
    score: float  # 0.0 - 1.0
    factors: Dict[str, float]  # 各要因のスコア
    suggested_agents: int  # 推奨エージェント数
    parallel_potential: float  # 並列化の可能性 (0.0 - 1.0)
    
@dataclass
class SubtaskDefinition:
    """サブタスクの定義"""
    task_type: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    estimated_time: float = 300.0
    priority: int = 5
    required_skills: List[str] = field(default_factory=list)

class TaskDecomposer:
    """タスク分解エンジン"""
    
    def __init__(self):
        # 複雑度分析のキーワードと重み
        self.complexity_keywords = {
            "simple": ["single", "basic", "simple", "check", "get", "list"],
            "moderate": ["analyze", "review", "update", "modify", "integrate"],
            "complex": ["refactor", "migrate", "implement", "design", "optimize"],
            "very_complex": ["rewrite", "architect", "overhaul", "redesign", "scale"]
        }
        
        # タスクタイプ別の分解戦略
        self.decomposition_strategies = {
            "code_review": self._decompose_code_review,
            "refactor": self._decompose_refactor,
            "test_generation": self._decompose_test_generation,
            "analysis": self._decompose_analysis,
            "implementation": self._decompose_implementation,
            "migration": self._decompose_migration,
            "optimization": self._decompose_optimization
        }
        
    def analyze_complexity(self, task: Task) -> ComplexityAnalysis:
        """タスクの複雑度を分析"""
        factors = {}
        
        # 1. 説明文の長さと複雑さ
        desc_length = len(task.description.split())
        factors["description_length"] = min(desc_length / 50.0, 1.0)
        
        # 2. ファイル数
        file_count = len(task.files) if task.files else 0
        factors["file_count"] = min(file_count / 10.0, 1.0)
        
        # 3. キーワード分析
        keyword_score = self._analyze_keywords(task.description)
        factors["keyword_complexity"] = keyword_score
        
        # 4. タスクタイプの複雑さ
        type_complexity = {
            "generic": 0.2,
            "code_review": 0.3,
            "test_generation": 0.4,
            "analysis": 0.5,
            "refactor": 0.7,
            "implementation": 0.8,
            "migration": 0.9,
            "optimization": 0.8
        }
        factors["task_type"] = type_complexity.get(task.task_type, 0.5)
        
        # 5. 並列化の可能性
        parallel_potential = self._estimate_parallel_potential(task)
        factors["parallel_potential"] = parallel_potential
        
        # 総合スコアの計算
        weights = {
            "description_length": 0.15,
            "file_count": 0.25,
            "keyword_complexity": 0.25,
            "task_type": 0.25,
            "parallel_potential": 0.10
        }
        
        total_score = sum(factors[k] * weights[k] for k in factors)
        
        # 複雑度レベルの決定
        if total_score < 0.3:
            complexity = TaskComplexity.SIMPLE
            suggested_agents = 1
        elif total_score < 0.5:
            complexity = TaskComplexity.MODERATE
            suggested_agents = 2
        elif total_score < 0.7:
            complexity = TaskComplexity.COMPLEX
            suggested_agents = 3
        else:
            complexity = TaskComplexity.VERY_COMPLEX
            suggested_agents = 5
            
        return ComplexityAnalysis(
            complexity=complexity,
            score=total_score,
            factors=factors,
            suggested_agents=suggested_agents,
            parallel_potential=parallel_potential
        )
        
    def decompose_task(
        self,
        task: Task,
        analysis: Optional[ComplexityAnalysis] = None
    ) -> List[SubtaskDefinition]:
        """タスクをサブタスクに分解"""
        if analysis is None:
            analysis = self.analyze_complexity(task)
            
        # シンプルなタスクは分解しない
        if analysis.complexity == TaskComplexity.SIMPLE:
            return []
            
        # タスクタイプ別の分解戦略を適用
        strategy = self.decomposition_strategies.get(
            task.task_type,
            self._decompose_generic
        )
        
        subtasks = strategy(task, analysis)
        
        # 並列化可能性に基づいて依存関係を調整
        if analysis.parallel_potential > 0.7:
            # 高い並列化可能性: 依存関係を最小化
            subtasks = self._minimize_dependencies(subtasks)
        else:
            # 低い並列化可能性: 順次実行を優先
            subtasks = self._chain_dependencies(subtasks)
            
        return subtasks
        
    def create_parallel_task(
        self,
        original_task: Task,
        subtasks: List[SubtaskDefinition]
    ) -> Task:
        """並列実行用のタスクを作成"""
        # サブタスクを辞書形式に変換
        subtask_dicts = []
        for i, subtask in enumerate(subtasks):
            subtask_dict = {
                "type": subtask.task_type,
                "description": subtask.description,
                "timeout": subtask.estimated_time,
                "priority": subtask.priority,
                "dependencies": subtask.dependencies,
                "subtask_id": f"{original_task.task_id}_sub_{i}"
            }
            
            # ファイルの割り当て
            if original_task.files:
                # ファイルを均等に分配
                files_per_subtask = len(original_task.files) // len(subtasks)
                start_idx = i * files_per_subtask
                end_idx = start_idx + files_per_subtask
                if i == len(subtasks) - 1:
                    end_idx = len(original_task.files)
                subtask_dict["files"] = original_task.files[start_idx:end_idx]
                
            subtask_dicts.append(subtask_dict)
            
        # 新しい並列タスクを作成
        parallel_task = Task(
            task_id=f"{original_task.task_id}_parallel",
            task_type=original_task.task_type,
            description=f"[Auto-decomposed] {original_task.description}",
            files=original_task.files,
            parallel=True,
            subtasks=subtask_dicts,
            priority=original_task.priority,
            timeout=max(s.estimated_time for s in subtasks)
        )
        
        return parallel_task
        
    def _analyze_keywords(self, description: str) -> float:
        """キーワードに基づく複雑度スコア"""
        description_lower = description.lower()
        scores = {
            "simple": 0.2,
            "moderate": 0.4,
            "complex": 0.7,
            "very_complex": 1.0
        }
        
        max_score = 0.2
        for level, keywords in self.complexity_keywords.items():
            if any(kw in description_lower for kw in keywords):
                max_score = max(max_score, scores[level])
                
        return max_score
        
    def _estimate_parallel_potential(self, task: Task) -> float:
        """並列化の可能性を推定"""
        score = 0.5  # ベーススコア
        
        # 複数ファイルは並列化しやすい
        if task.files and len(task.files) > 1:
            score += 0.2
            
        # 独立したアクションを示すキーワード
        parallel_keywords = ["each", "all", "multiple", "every", "separate"]
        if any(kw in task.description.lower() for kw in parallel_keywords):
            score += 0.2
            
        # 順次処理を示すキーワード
        sequential_keywords = ["then", "after", "before", "step by step", "sequentially"]
        if any(kw in task.description.lower() for kw in sequential_keywords):
            score -= 0.3
            
        return max(0.0, min(1.0, score))
        
    def _decompose_code_review(
        self,
        task: Task,
        analysis: ComplexityAnalysis
    ) -> List[SubtaskDefinition]:
        """コードレビュータスクの分解"""
        subtasks = []
        
        # 静的解析
        subtasks.append(SubtaskDefinition(
            task_type="analysis",
            description="Perform static code analysis and linting",
            estimated_time=180.0,
            priority=8,
            required_skills=["static_analysis", "linting"]
        ))
        
        # セキュリティレビュー
        subtasks.append(SubtaskDefinition(
            task_type="code_review",
            description="Security vulnerability assessment",
            estimated_time=300.0,
            priority=9,
            required_skills=["security", "vulnerability_analysis"]
        ))
        
        # パフォーマンスレビュー
        if analysis.complexity in [TaskComplexity.COMPLEX, TaskComplexity.VERY_COMPLEX]:
            subtasks.append(SubtaskDefinition(
                task_type="analysis",
                description="Performance analysis and optimization suggestions",
                estimated_time=240.0,
                priority=7,
                required_skills=["performance", "profiling"]
            ))
            
        # アーキテクチャレビュー
        if analysis.complexity == TaskComplexity.VERY_COMPLEX:
            subtasks.append(SubtaskDefinition(
                task_type="code_review",
                description="Architecture and design pattern review",
                estimated_time=360.0,
                priority=8,
                required_skills=["architecture", "design_patterns"]
            ))
            
        return subtasks
        
    def _decompose_refactor(
        self,
        task: Task,
        analysis: ComplexityAnalysis
    ) -> List[SubtaskDefinition]:
        """リファクタリングタスクの分解"""
        subtasks = []
        
        # 分析フェーズ
        subtasks.append(SubtaskDefinition(
            task_type="analysis",
            description="Analyze code structure and identify refactoring opportunities",
            estimated_time=240.0,
            priority=9,
            required_skills=["code_analysis", "pattern_recognition"]
        ))
        
        # テスト作成
        subtasks.append(SubtaskDefinition(
            task_type="test_generation",
            description="Generate tests to ensure behavior preservation",
            dependencies=["0"],  # 分析の後
            estimated_time=300.0,
            priority=8,
            required_skills=["testing", "test_generation"]
        ))
        
        # リファクタリング実行
        subtasks.append(SubtaskDefinition(
            task_type="refactor",
            description="Execute refactoring with safety checks",
            dependencies=["1"],  # テストの後
            estimated_time=420.0,
            priority=9,
            required_skills=["refactoring", "code_transformation"]
        ))
        
        # 検証
        subtasks.append(SubtaskDefinition(
            task_type="test_generation",
            description="Verify refactoring and run all tests",
            dependencies=["2"],  # リファクタリングの後
            estimated_time=180.0,
            priority=8,
            required_skills=["testing", "validation"]
        ))
        
        return subtasks
        
    def _decompose_test_generation(
        self,
        task: Task,
        analysis: ComplexityAnalysis
    ) -> List[SubtaskDefinition]:
        """テスト生成タスクの分解"""
        subtasks = []
        
        # コード分析
        subtasks.append(SubtaskDefinition(
            task_type="analysis",
            description="Analyze code structure and identify test scenarios",
            estimated_time=180.0,
            priority=8,
            required_skills=["code_analysis", "test_planning"]
        ))
        
        # ユニットテスト生成
        subtasks.append(SubtaskDefinition(
            task_type="test_generation",
            description="Generate unit tests for individual functions",
            dependencies=["0"],
            estimated_time=300.0,
            priority=9,
            required_skills=["unit_testing", "test_generation"]
        ))
        
        # 統合テスト生成
        if analysis.complexity in [TaskComplexity.COMPLEX, TaskComplexity.VERY_COMPLEX]:
            subtasks.append(SubtaskDefinition(
                task_type="test_generation",
                description="Generate integration tests",
                dependencies=["0"],
                estimated_time=360.0,
                priority=7,
                required_skills=["integration_testing", "test_generation"]
            ))
            
        return subtasks
        
    def _decompose_analysis(
        self,
        task: Task,
        analysis: ComplexityAnalysis
    ) -> List[SubtaskDefinition]:
        """分析タスクの分解"""
        subtasks = []
        
        # データ収集
        subtasks.append(SubtaskDefinition(
            task_type="analysis",
            description="Collect and preprocess data for analysis",
            estimated_time=180.0,
            priority=8,
            required_skills=["data_collection", "preprocessing"]
        ))
        
        # 複雑度に応じた分析
        if analysis.complexity == TaskComplexity.MODERATE:
            subtasks.append(SubtaskDefinition(
                task_type="analysis",
                description="Perform basic statistical analysis",
                dependencies=["0"],
                estimated_time=240.0,
                priority=7,
                required_skills=["statistics", "data_analysis"]
            ))
        else:
            # 複数の並列分析
            subtasks.extend([
                SubtaskDefinition(
                    task_type="analysis",
                    description="Perform structural analysis",
                    dependencies=["0"],
                    estimated_time=300.0,
                    priority=8,
                    required_skills=["structural_analysis"]
                ),
                SubtaskDefinition(
                    task_type="analysis",
                    description="Perform behavioral analysis",
                    dependencies=["0"],
                    estimated_time=300.0,
                    priority=8,
                    required_skills=["behavioral_analysis"]
                ),
                SubtaskDefinition(
                    task_type="analysis",
                    description="Generate insights and recommendations",
                    dependencies=["1", "2"],
                    estimated_time=240.0,
                    priority=9,
                    required_skills=["synthesis", "recommendation"]
                )
            ])
            
        return subtasks
        
    def _decompose_implementation(
        self,
        task: Task,
        analysis: ComplexityAnalysis
    ) -> List[SubtaskDefinition]:
        """実装タスクの分解"""
        subtasks = []
        
        # 設計フェーズ
        subtasks.append(SubtaskDefinition(
            task_type="analysis",
            description="Design architecture and create implementation plan",
            estimated_time=300.0,
            priority=9,
            required_skills=["architecture", "design"]
        ))
        
        # コア実装
        subtasks.append(SubtaskDefinition(
            task_type="implementation",
            description="Implement core functionality",
            dependencies=["0"],
            estimated_time=600.0,
            priority=9,
            required_skills=["programming", "implementation"]
        ))
        
        # テスト作成
        subtasks.append(SubtaskDefinition(
            task_type="test_generation",
            description="Create comprehensive test suite",
            dependencies=["1"],
            estimated_time=300.0,
            priority=8,
            required_skills=["testing", "test_design"]
        ))
        
        # ドキュメント作成
        subtasks.append(SubtaskDefinition(
            task_type="documentation",
            description="Create documentation and usage examples",
            dependencies=["1"],
            estimated_time=240.0,
            priority=6,
            required_skills=["documentation", "technical_writing"]
        ))
        
        return subtasks
        
    def _decompose_migration(
        self,
        task: Task,
        analysis: ComplexityAnalysis
    ) -> List[SubtaskDefinition]:
        """マイグレーションタスクの分解"""
        subtasks = []
        
        # 現状分析
        subtasks.append(SubtaskDefinition(
            task_type="analysis",
            description="Analyze current system and migration requirements",
            estimated_time=360.0,
            priority=9,
            required_skills=["system_analysis", "migration_planning"]
        ))
        
        # 互換性チェック
        subtasks.append(SubtaskDefinition(
            task_type="analysis",
            description="Check compatibility and identify breaking changes",
            dependencies=["0"],
            estimated_time=300.0,
            priority=9,
            required_skills=["compatibility_analysis", "risk_assessment"]
        ))
        
        # マイグレーションスクリプト作成
        subtasks.append(SubtaskDefinition(
            task_type="implementation",
            description="Create migration scripts and tools",
            dependencies=["1"],
            estimated_time=480.0,
            priority=8,
            required_skills=["scripting", "automation"]
        ))
        
        # テストマイグレーション
        subtasks.append(SubtaskDefinition(
            task_type="test_generation",
            description="Test migration in isolated environment",
            dependencies=["2"],
            estimated_time=360.0,
            priority=9,
            required_skills=["testing", "migration_testing"]
        ))
        
        # ロールバック計画
        subtasks.append(SubtaskDefinition(
            task_type="implementation",
            description="Create rollback procedures",
            dependencies=["2"],
            estimated_time=240.0,
            priority=8,
            required_skills=["disaster_recovery", "planning"]
        ))
        
        return subtasks
        
    def _decompose_optimization(
        self,
        task: Task,
        analysis: ComplexityAnalysis
    ) -> List[SubtaskDefinition]:
        """最適化タスクの分解"""
        subtasks = []
        
        # パフォーマンス分析
        subtasks.append(SubtaskDefinition(
            task_type="analysis",
            description="Profile and identify performance bottlenecks",
            estimated_time=300.0,
            priority=9,
            required_skills=["profiling", "performance_analysis"]
        ))
        
        # 最適化戦略
        subtasks.append(SubtaskDefinition(
            task_type="analysis",
            description="Develop optimization strategies",
            dependencies=["0"],
            estimated_time=240.0,
            priority=8,
            required_skills=["optimization", "algorithm_design"]
        ))
        
        # 実装
        subtasks.append(SubtaskDefinition(
            task_type="implementation",
            description="Implement optimizations",
            dependencies=["1"],
            estimated_time=480.0,
            priority=9,
            required_skills=["optimization", "performance_tuning"]
        ))
        
        # ベンチマーク
        subtasks.append(SubtaskDefinition(
            task_type="test_generation",
            description="Create benchmarks and verify improvements",
            dependencies=["2"],
            estimated_time=240.0,
            priority=8,
            required_skills=["benchmarking", "performance_testing"]
        ))
        
        return subtasks
        
    def _decompose_generic(
        self,
        task: Task,
        analysis: ComplexityAnalysis
    ) -> List[SubtaskDefinition]:
        """汎用タスクの分解"""
        # ファイル数に基づいて分解
        if task.files and len(task.files) > 1:
            subtasks = []
            for i, file in enumerate(task.files):
                subtasks.append(SubtaskDefinition(
                    task_type=task.task_type,
                    description=f"{task.description} - {file}",
                    estimated_time=task.timeout / len(task.files),
                    priority=task.priority
                ))
            return subtasks
            
        # 複雑度に基づいて段階的に分解
        if analysis.complexity == TaskComplexity.MODERATE:
            return [
                SubtaskDefinition(
                    task_type="analysis",
                    description=f"Analyze requirements for: {task.description}",
                    estimated_time=task.timeout * 0.3,
                    priority=task.priority
                ),
                SubtaskDefinition(
                    task_type=task.task_type,
                    description=f"Execute: {task.description}",
                    dependencies=["0"],
                    estimated_time=task.timeout * 0.7,
                    priority=task.priority
                )
            ]
        elif analysis.complexity in [TaskComplexity.COMPLEX, TaskComplexity.VERY_COMPLEX]:
            return [
                SubtaskDefinition(
                    task_type="analysis",
                    description=f"Planning phase for: {task.description}",
                    estimated_time=task.timeout * 0.2,
                    priority=task.priority
                ),
                SubtaskDefinition(
                    task_type=task.task_type,
                    description=f"Implementation phase 1: {task.description}",
                    dependencies=["0"],
                    estimated_time=task.timeout * 0.4,
                    priority=task.priority
                ),
                SubtaskDefinition(
                    task_type=task.task_type,
                    description=f"Implementation phase 2: {task.description}",
                    dependencies=["0"],
                    estimated_time=task.timeout * 0.3,
                    priority=task.priority
                ),
                SubtaskDefinition(
                    task_type="analysis",
                    description=f"Validation and integration: {task.description}",
                    dependencies=["1", "2"],
                    estimated_time=task.timeout * 0.1,
                    priority=task.priority
                )
            ]
            
        return []
        
    def _minimize_dependencies(
        self,
        subtasks: List[SubtaskDefinition]
    ) -> List[SubtaskDefinition]:
        """依存関係を最小化して並列実行を最大化"""
        # 分析タスクとそれ以外を分離
        analysis_tasks = []
        other_tasks = []
        
        for i, subtask in enumerate(subtasks):
            if subtask.task_type == "analysis" and not subtask.dependencies:
                analysis_tasks.append(i)
            else:
                other_tasks.append(i)
                
        # 他のタスクの依存関係を分析タスクのみに変更
        for i in other_tasks:
            if subtasks[i].dependencies:
                # 既存の依存関係が分析タスクでない場合、最小化
                new_deps = []
                for dep in subtasks[i].dependencies:
                    if int(dep) in analysis_tasks:
                        new_deps.append(dep)
                if new_deps:
                    subtasks[i].dependencies = new_deps
                elif analysis_tasks:
                    # 依存関係がない場合、最初の分析タスクに依存
                    subtasks[i].dependencies = [str(analysis_tasks[0])]
                    
        return subtasks
        
    def _chain_dependencies(
        self,
        subtasks: List[SubtaskDefinition]
    ) -> List[SubtaskDefinition]:
        """順次実行のために依存関係をチェーン化"""
        for i in range(1, len(subtasks)):
            if not subtasks[i].dependencies:
                subtasks[i].dependencies = [str(i-1)]
                
        return subtasks