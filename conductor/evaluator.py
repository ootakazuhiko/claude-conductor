#!/usr/bin/env python3
"""
LLM-as-judge評価システム
タスク出力の自動品質評価とフィードバック生成
"""

import time
import json
import sqlite3
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
from enum import Enum
from datetime import datetime, timedelta
import logging
import asyncio
from collections import defaultdict
import re
import statistics

logger = logging.getLogger(__name__)

class EvaluationCriteria(Enum):
    """評価基準"""
    CORRECTNESS = "correctness"
    COMPLETENESS = "completeness"
    CLARITY = "clarity"
    EFFICIENCY = "efficiency"
    STYLE = "style"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    PERFORMANCE = "performance"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    CREATIVITY = "creativity"
    RELEVANCE = "relevance"
    SAFETY = "safety"

@dataclass
class CriteriaDefinition:
    """評価基準の定義"""
    name: str
    description: str
    weight: float  # 0.0-1.0
    max_score: int = 10
    evaluation_prompt: str = ""
    
@dataclass
class EvaluationTemplate:
    """評価テンプレート"""
    task_type: str
    criteria: List[CriteriaDefinition]
    overall_prompt: str
    context_requirements: List[str] = field(default_factory=list)
    
    def get_total_weight(self) -> float:
        """総重みを取得"""
        return sum(c.weight for c in self.criteria)

@dataclass
class CriteriaScore:
    """基準別スコア"""
    criteria: str
    score: int
    max_score: int
    weight: float
    feedback: str
    suggestions: List[str] = field(default_factory=list)
    
    @property
    def weighted_score(self) -> float:
        """重み付きスコア"""
        return (self.score / self.max_score) * self.weight * 100

@dataclass
class EvaluationResult:
    """評価結果"""
    task_id: str
    agent_id: str
    task_type: str
    overall_score: float  # 0-100
    criteria_scores: List[CriteriaScore]
    overall_feedback: str
    improvement_suggestions: List[str]
    evaluation_timestamp: float = field(default_factory=time.time)
    evaluator_id: str = "llm_judge"
    confidence_level: float = 0.8  # 0.0-1.0
    
    @property
    def grade(self) -> str:
        """グレード"""
        if self.overall_score >= 90:
            return "A"
        elif self.overall_score >= 80:
            return "B"
        elif self.overall_score >= 70:
            return "C"
        elif self.overall_score >= 60:
            return "D"
        else:
            return "F"

@dataclass
class QualityTrend:
    """品質トレンド分析"""
    agent_id: str
    task_type: str
    time_period: str
    average_score: float
    score_trend: str  # "improving", "declining", "stable"
    evaluation_count: int
    best_score: float
    worst_score: float
    common_issues: List[str]

class LLMJudgeEvaluator:
    """LLM-as-judge評価システム"""
    
    def __init__(self, db_path: str = "/tmp/evaluation_results.db"):
        self.db_path = db_path
        self._init_db()
        
        # 評価テンプレート
        self.templates = self._load_default_templates()
        
        # 評価統計
        self.evaluation_stats = {
            "total_evaluations": 0,
            "average_score": 0.0,
            "evaluations_by_type": defaultdict(int),
            "evaluations_by_agent": defaultdict(int)
        }
        
    def _init_db(self):
        """データベースを初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                overall_score REAL NOT NULL,
                overall_feedback TEXT,
                improvement_suggestions TEXT,
                evaluation_timestamp REAL NOT NULL,
                evaluator_id TEXT NOT NULL,
                confidence_level REAL NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS criteria_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER REFERENCES evaluations(id),
                criteria TEXT NOT NULL,
                score INTEGER NOT NULL,
                max_score INTEGER NOT NULL,
                weight REAL NOT NULL,
                feedback TEXT,
                suggestions TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_id ON evaluations(task_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_id ON evaluations(agent_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON evaluations(evaluation_timestamp)
        """)
        
        conn.commit()
        conn.close()
        
    def _load_default_templates(self) -> Dict[str, EvaluationTemplate]:
        """デフォルト評価テンプレートを読み込み"""
        templates = {}
        
        # コードレビュー用テンプレート
        templates["code_review"] = EvaluationTemplate(
            task_type="code_review",
            criteria=[
                CriteriaDefinition(
                    name="correctness",
                    description="Issues identified are valid and accurately described",
                    weight=0.3,
                    evaluation_prompt="How accurate and valid are the identified issues?"
                ),
                CriteriaDefinition(
                    name="completeness",
                    description="All significant issues have been identified",
                    weight=0.25,
                    evaluation_prompt="Are all major issues covered?"
                ),
                CriteriaDefinition(
                    name="clarity",
                    description="Feedback is clear and actionable",
                    weight=0.2,
                    evaluation_prompt="How clear and actionable is the feedback?"
                ),
                CriteriaDefinition(
                    name="security",
                    description="Security issues are properly identified",
                    weight=0.15,
                    evaluation_prompt="Are security concerns adequately addressed?"
                ),
                CriteriaDefinition(
                    name="style",
                    description="Code style and best practices are evaluated",
                    weight=0.1,
                    evaluation_prompt="Are style issues properly identified?"
                )
            ],
            overall_prompt="Evaluate the quality of this code review output based on accuracy, completeness, and actionability."
        )
        
        # リファクタリング用テンプレート
        templates["refactor"] = EvaluationTemplate(
            task_type="refactor",
            criteria=[
                CriteriaDefinition(
                    name="correctness",
                    description="Refactored code maintains original functionality",
                    weight=0.35,
                    evaluation_prompt="Does the refactored code preserve original behavior?"
                ),
                CriteriaDefinition(
                    name="maintainability",
                    description="Code is more maintainable after refactoring",
                    weight=0.25,
                    evaluation_prompt="Is the code more maintainable and readable?"
                ),
                CriteriaDefinition(
                    name="efficiency",
                    description="Performance is maintained or improved",
                    weight=0.2,
                    evaluation_prompt="Are performance characteristics preserved or improved?"
                ),
                CriteriaDefinition(
                    name="style",
                    description="Code follows consistent style guidelines",
                    weight=0.2,
                    evaluation_prompt="Does the code follow consistent style patterns?"
                )
            ],
            overall_prompt="Evaluate the quality of this refactoring based on correctness, maintainability, and code quality."
        )
        
        # テスト生成用テンプレート
        templates["test_generation"] = EvaluationTemplate(
            task_type="test_generation",
            criteria=[
                CriteriaDefinition(
                    name="completeness",
                    description="Tests cover all major functionality",
                    weight=0.3,
                    evaluation_prompt="Do tests cover all important code paths?"
                ),
                CriteriaDefinition(
                    name="correctness",
                    description="Tests are syntactically correct and executable",
                    weight=0.25,
                    evaluation_prompt="Are the tests syntactically correct?"
                ),
                CriteriaDefinition(
                    name="clarity",
                    description="Tests are well-structured and readable",
                    weight=0.2,
                    evaluation_prompt="Are tests clear and well-organized?"
                ),
                CriteriaDefinition(
                    name="edge_cases",
                    description="Edge cases and error conditions are tested",
                    weight=0.15,
                    evaluation_prompt="Are edge cases and error conditions covered?"
                ),
                CriteriaDefinition(
                    name="maintainability",
                    description="Tests are maintainable and follow best practices",
                    weight=0.1,
                    evaluation_prompt="Do tests follow testing best practices?"
                )
            ],
            overall_prompt="Evaluate the quality of generated tests based on coverage, correctness, and maintainability."
        )
        
        # 分析用テンプレート
        templates["analysis"] = EvaluationTemplate(
            task_type="analysis",
            criteria=[
                CriteriaDefinition(
                    name="accuracy",
                    description="Analysis findings are accurate and relevant",
                    weight=0.3,
                    evaluation_prompt="How accurate are the analysis findings?"
                ),
                CriteriaDefinition(
                    name="depth",
                    description="Analysis provides sufficient depth and insight",
                    weight=0.25,
                    evaluation_prompt="Does the analysis provide meaningful insights?"
                ),
                CriteriaDefinition(
                    name="clarity",
                    description="Analysis is clearly presented and understandable",
                    weight=0.2,
                    evaluation_prompt="Is the analysis clear and well-presented?"
                ),
                CriteriaDefinition(
                    name="actionability",
                    description="Analysis provides actionable recommendations",
                    weight=0.15,
                    evaluation_prompt="Are the recommendations actionable?"
                ),
                CriteriaDefinition(
                    name="completeness",
                    description="Analysis covers all relevant aspects",
                    weight=0.1,
                    evaluation_prompt="Are all relevant aspects covered?"
                )
            ],
            overall_prompt="Evaluate the quality of this analysis based on accuracy, depth, and actionability."
        )
        
        # 汎用テンプレート
        templates["generic"] = EvaluationTemplate(
            task_type="generic",
            criteria=[
                CriteriaDefinition(
                    name="correctness",
                    description="Output correctly addresses the task requirements",
                    weight=0.4,
                    evaluation_prompt="Does the output correctly address the task?"
                ),
                CriteriaDefinition(
                    name="completeness",
                    description="All aspects of the task are covered",
                    weight=0.3,
                    evaluation_prompt="Are all task aspects covered?"
                ),
                CriteriaDefinition(
                    name="clarity",
                    description="Output is clear and well-structured",
                    weight=0.3,
                    evaluation_prompt="Is the output clear and well-organized?"
                )
            ],
            overall_prompt="Evaluate the overall quality of this task output."
        )
        
        return templates
    
    async def evaluate_task_result(
        self,
        task_id: str,
        agent_id: str,
        task_input: Dict[str, Any],
        task_output: Dict[str, Any],
        task_type: str = "generic"
    ) -> EvaluationResult:
        """タスク結果を評価"""
        logger.info(f"Evaluating task {task_id} of type {task_type}")
        
        # 評価テンプレートを取得
        template = self.templates.get(task_type, self.templates["generic"])
        
        # 各基準で評価
        criteria_scores = []
        for criteria_def in template.criteria:
            score = await self._evaluate_criteria(
                criteria_def,
                task_input,
                task_output,
                task_type
            )
            criteria_scores.append(score)
        
        # 総合スコアを計算
        total_weighted_score = sum(score.weighted_score for score in criteria_scores)
        total_weight = sum(score.weight for score in criteria_scores)
        overall_score = total_weighted_score / total_weight if total_weight > 0 else 0
        
        # 総合フィードバックを生成
        overall_feedback = await self._generate_overall_feedback(
            template,
            criteria_scores,
            task_input,
            task_output
        )
        
        # 改善提案を生成
        improvement_suggestions = self._generate_improvement_suggestions(criteria_scores)
        
        # 評価結果を作成
        result = EvaluationResult(
            task_id=task_id,
            agent_id=agent_id,
            task_type=task_type,
            overall_score=overall_score,
            criteria_scores=criteria_scores,
            overall_feedback=overall_feedback,
            improvement_suggestions=improvement_suggestions,
            confidence_level=self._calculate_confidence(criteria_scores)
        )
        
        # データベースに保存
        self._save_evaluation_result(result)
        
        # 統計を更新
        self._update_stats(result)
        
        logger.info(f"Task {task_id} evaluated with score {overall_score:.1f}")
        return result
    
    async def _evaluate_criteria(
        self,
        criteria_def: CriteriaDefinition,
        task_input: Dict[str, Any],
        task_output: Dict[str, Any],
        task_type: str
    ) -> CriteriaScore:
        """単一基準での評価"""
        # シミュレートされた評価（実際の実装では LLM API を呼び出す）
        score = await self._simulate_llm_evaluation(
            criteria_def,
            task_input,
            task_output,
            task_type
        )
        
        feedback = self._generate_criteria_feedback(criteria_def, score, task_output)
        suggestions = self._generate_criteria_suggestions(criteria_def, score, task_output)
        
        return CriteriaScore(
            criteria=criteria_def.name,
            score=score,
            max_score=criteria_def.max_score,
            weight=criteria_def.weight,
            feedback=feedback,
            suggestions=suggestions
        )
    
    async def _simulate_llm_evaluation(
        self,
        criteria_def: CriteriaDefinition,
        task_input: Dict[str, Any],
        task_output: Dict[str, Any],
        task_type: str
    ) -> int:
        """LLM評価をシミュレート（実際の実装では LLM API を使用）"""
        # タスクタイプと基準に基づいてスコアを生成
        base_score = 7  # ベーススコア
        
        # タスクタイプ別の調整
        if task_type == "code_review":
            if criteria_def.name == "correctness":
                base_score += 1
            elif criteria_def.name == "security":
                base_score += 0.5
        elif task_type == "refactor":
            if criteria_def.name == "maintainability":
                base_score += 1
            elif criteria_def.name == "efficiency":
                base_score += 0.5
        elif task_type == "test_generation":
            if criteria_def.name == "completeness":
                base_score += 1
        
        # 出力の品質に基づく調整
        output_quality = self._assess_output_quality(task_output)
        base_score += output_quality
        
        # ランダムな変動を追加（実際の評価の不確実性をシミュレート）
        import random
        variation = random.uniform(-1, 1)
        final_score = max(1, min(criteria_def.max_score, int(base_score + variation)))
        
        return final_score
    
    def _assess_output_quality(self, task_output: Dict[str, Any]) -> float:
        """出力品質を簡易評価"""
        quality_score = 0.0
        
        # 出力の複雑さと完全性をチェック
        if isinstance(task_output.get("result"), dict):
            result = task_output["result"]
            
            # キーの数に基づく評価
            if len(result) > 3:
                quality_score += 0.5
            
            # テキストの長さに基づく評価
            for value in result.values():
                if isinstance(value, str) and len(value) > 100:
                    quality_score += 0.3
                    break
            
            # 特定のキーワードの存在チェック
            result_str = str(result).lower()
            if any(keyword in result_str for keyword in ["error", "issue", "problem", "improvement"]):
                quality_score += 0.5
        
        return min(2.0, quality_score)
    
    def _generate_criteria_feedback(
        self,
        criteria_def: CriteriaDefinition,
        score: int,
        task_output: Dict[str, Any]
    ) -> str:
        """基準別フィードバックを生成"""
        feedback_templates = {
            "correctness": {
                "high": "The output demonstrates high accuracy and correctness.",
                "medium": "The output is generally correct with minor issues.",
                "low": "The output contains several accuracy issues that need attention."
            },
            "completeness": {
                "high": "The output comprehensively addresses all aspects of the task.",
                "medium": "The output covers most aspects but may miss some details.",
                "low": "The output is incomplete and misses significant aspects."
            },
            "clarity": {
                "high": "The output is exceptionally clear and well-structured.",
                "medium": "The output is generally clear with room for improvement.",
                "low": "The output lacks clarity and structure."
            }
        }
        
        # スコアレベルを決定
        if score >= 8:
            level = "high"
        elif score >= 5:
            level = "medium"
        else:
            level = "low"
        
        # テンプレートからフィードバックを取得
        templates = feedback_templates.get(criteria_def.name, feedback_templates["correctness"])
        return templates.get(level, f"Score: {score}/{criteria_def.max_score}")
    
    def _generate_criteria_suggestions(
        self,
        criteria_def: CriteriaDefinition,
        score: int,
        task_output: Dict[str, Any]
    ) -> List[str]:
        """基準別改善提案を生成"""
        if score >= 8:
            return []  # 高スコアの場合は提案不要
        
        suggestion_templates = {
            "correctness": [
                "Review and verify the accuracy of identified issues",
                "Cross-check findings with established standards",
                "Consider edge cases and corner conditions"
            ],
            "completeness": [
                "Ensure all aspects of the task are addressed",
                "Review the requirements to identify missing elements",
                "Add more comprehensive coverage"
            ],
            "clarity": [
                "Improve the structure and organization of the output",
                "Use clearer language and explanations",
                "Add more detailed descriptions where needed"
            ],
            "security": [
                "Review security implications more thoroughly",
                "Consider additional security vulnerabilities",
                "Add security best practices recommendations"
            ],
            "maintainability": [
                "Focus on code readability and structure",
                "Consider long-term maintenance implications",
                "Apply consistent coding patterns"
            ]
        }
        
        suggestions = suggestion_templates.get(criteria_def.name, [])
        # スコアに基づいて提案数を調整
        max_suggestions = 3 if score < 5 else 1
        return suggestions[:max_suggestions]
    
    async def _generate_overall_feedback(
        self,
        template: EvaluationTemplate,
        criteria_scores: List[CriteriaScore],
        task_input: Dict[str, Any],
        task_output: Dict[str, Any]
    ) -> str:
        """総合フィードバックを生成"""
        # 強み・弱みを分析
        strengths = []
        weaknesses = []
        
        for score in criteria_scores:
            if score.score >= 8:
                strengths.append(f"{score.criteria} ({score.score}/{score.max_score})")
            elif score.score < 6:
                weaknesses.append(f"{score.criteria} ({score.score}/{score.max_score})")
        
        feedback_parts = []
        
        if strengths:
            feedback_parts.append(f"Strengths: {', '.join(strengths)}")
        
        if weaknesses:
            feedback_parts.append(f"Areas for improvement: {', '.join(weaknesses)}")
        
        # 総合的なコメント
        overall_score = sum(score.weighted_score for score in criteria_scores) / sum(score.weight for score in criteria_scores)
        
        if overall_score >= 85:
            overall_comment = "Excellent work with high quality output."
        elif overall_score >= 70:
            overall_comment = "Good work with room for minor improvements."
        elif overall_score >= 60:
            overall_comment = "Adequate work with several areas for improvement."
        else:
            overall_comment = "Significant improvements needed to meet quality standards."
        
        feedback_parts.append(overall_comment)
        
        return " ".join(feedback_parts)
    
    def _generate_improvement_suggestions(
        self,
        criteria_scores: List[CriteriaScore]
    ) -> List[str]:
        """改善提案を生成"""
        suggestions = []
        
        # 各基準の提案を重要度順に収集
        for score in sorted(criteria_scores, key=lambda s: s.score):
            suggestions.extend(score.suggestions)
        
        # 重複を除去し、最大5つまで
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion not in unique_suggestions:
                unique_suggestions.append(suggestion)
        
        return unique_suggestions[:5]
    
    def _calculate_confidence(self, criteria_scores: List[CriteriaScore]) -> float:
        """評価の信頼度を計算"""
        # スコアの分散に基づいて信頼度を計算
        scores = [score.score for score in criteria_scores]
        if not scores:
            return 0.5
        
        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        
        # 分散が小さいほど信頼度が高い
        confidence = max(0.5, 1.0 - (variance / 25))  # 最大分散を25と仮定
        return min(1.0, confidence)
    
    def _save_evaluation_result(self, result: EvaluationResult):
        """評価結果をデータベースに保存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # メイン評価を挿入
        cursor.execute("""
            INSERT INTO evaluations (
                task_id, agent_id, task_type, overall_score, overall_feedback,
                improvement_suggestions, evaluation_timestamp, evaluator_id, confidence_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.task_id,
            result.agent_id,
            result.task_type,
            result.overall_score,
            result.overall_feedback,
            json.dumps(result.improvement_suggestions),
            result.evaluation_timestamp,
            result.evaluator_id,
            result.confidence_level
        ))
        
        evaluation_id = cursor.lastrowid
        
        # 基準別スコアを挿入
        for score in result.criteria_scores:
            cursor.execute("""
                INSERT INTO criteria_scores (
                    evaluation_id, criteria, score, max_score, weight, feedback, suggestions
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                evaluation_id,
                score.criteria,
                score.score,
                score.max_score,
                score.weight,
                score.feedback,
                json.dumps(score.suggestions)
            ))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Saved evaluation result for task {result.task_id}")
    
    def _update_stats(self, result: EvaluationResult):
        """統計を更新"""
        self.evaluation_stats["total_evaluations"] += 1
        self.evaluation_stats["evaluations_by_type"][result.task_type] += 1
        self.evaluation_stats["evaluations_by_agent"][result.agent_id] += 1
        
        # 平均スコアを更新
        total = self.evaluation_stats["total_evaluations"]
        current_avg = self.evaluation_stats["average_score"]
        new_avg = ((current_avg * (total - 1)) + result.overall_score) / total
        self.evaluation_stats["average_score"] = new_avg
    
    def get_evaluation_history(
        self,
        agent_id: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 50
    ) -> List[EvaluationResult]:
        """評価履歴を取得"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT * FROM evaluations
            WHERE 1=1
        """
        params = []
        
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        
        if task_type:
            query += " AND task_type = ?"
            params.append(task_type)
        
        query += " ORDER BY evaluation_timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        results = []
        
        for row in cursor.fetchall():
            # 基準別スコアを取得
            cursor.execute("""
                SELECT * FROM criteria_scores WHERE evaluation_id = ?
            """, (row[0],))
            
            criteria_rows = cursor.fetchall()
            criteria_scores = []
            
            for criteria_row in criteria_rows:
                criteria_scores.append(CriteriaScore(
                    criteria=criteria_row[2],
                    score=criteria_row[3],
                    max_score=criteria_row[4],
                    weight=criteria_row[5],
                    feedback=criteria_row[6],
                    suggestions=json.loads(criteria_row[7]) if criteria_row[7] else []
                ))
            
            result = EvaluationResult(
                task_id=row[1],
                agent_id=row[2],
                task_type=row[3],
                overall_score=row[4],
                criteria_scores=criteria_scores,
                overall_feedback=row[5],
                improvement_suggestions=json.loads(row[6]) if row[6] else [],
                evaluation_timestamp=row[7],
                evaluator_id=row[8],
                confidence_level=row[9]
            )
            results.append(result)
        
        conn.close()
        return results
    
    def analyze_quality_trends(
        self,
        time_period: str = "week",
        min_evaluations: int = 5
    ) -> List[QualityTrend]:
        """品質トレンドを分析"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 時間範囲を設定
        if time_period == "day":
            start_time = time.time() - 86400
        elif time_period == "week":
            start_time = time.time() - 604800
        elif time_period == "month":
            start_time = time.time() - 2592000
        else:
            start_time = 0
        
        # エージェント・タスクタイプ別の品質トレンドを取得
        cursor.execute("""
            SELECT 
                agent_id,
                task_type,
                AVG(overall_score) as avg_score,
                COUNT(*) as eval_count,
                MAX(overall_score) as best_score,
                MIN(overall_score) as worst_score
            FROM evaluations
            WHERE evaluation_timestamp >= ?
            GROUP BY agent_id, task_type
            HAVING eval_count >= ?
        """, (start_time, min_evaluations))
        
        trends = []
        for row in cursor.fetchall():
            agent_id, task_type, avg_score, eval_count, best_score, worst_score = row
            
            # トレンド方向を計算（簡易版：最近の評価 vs 古い評価）
            cursor.execute("""
                SELECT overall_score, evaluation_timestamp
                FROM evaluations
                WHERE agent_id = ? AND task_type = ? AND evaluation_timestamp >= ?
                ORDER BY evaluation_timestamp
            """, (agent_id, task_type, start_time))
            
            scores_data = cursor.fetchall()
            if len(scores_data) >= 3:
                # 前半と後半の平均を比較
                mid_point = len(scores_data) // 2
                early_avg = sum(score[0] for score in scores_data[:mid_point]) / mid_point
                recent_avg = sum(score[0] for score in scores_data[mid_point:]) / (len(scores_data) - mid_point)
                
                if recent_avg > early_avg + 2:
                    trend_direction = "improving"
                elif recent_avg < early_avg - 2:
                    trend_direction = "declining"
                else:
                    trend_direction = "stable"
            else:
                trend_direction = "stable"
            
            # 共通の問題を分析
            cursor.execute("""
                SELECT criteria_scores.criteria, AVG(criteria_scores.score) as avg_criteria_score
                FROM criteria_scores
                JOIN evaluations ON criteria_scores.evaluation_id = evaluations.id
                WHERE evaluations.agent_id = ? AND evaluations.task_type = ? 
                AND evaluations.evaluation_timestamp >= ?
                GROUP BY criteria_scores.criteria
                HAVING AVG(criteria_scores.score) < 6
            """, (agent_id, task_type, start_time))
            
            common_issues = [f"Low {row[0]} score (avg: {row[1]:.1f})" for row in cursor.fetchall()]
            
            trend = QualityTrend(
                agent_id=agent_id,
                task_type=task_type,
                time_period=time_period,
                average_score=avg_score,
                score_trend=trend_direction,
                evaluation_count=eval_count,
                best_score=best_score,
                worst_score=worst_score,
                common_issues=common_issues
            )
            trends.append(trend)
        
        conn.close()
        return trends
    
    async def batch_evaluate(
        self,
        tasks: List[Tuple[str, str, Dict[str, Any], Dict[str, Any], str]]
    ) -> List[EvaluationResult]:
        """バッチ評価"""
        results = []
        
        for task_id, agent_id, task_input, task_output, task_type in tasks:
            try:
                result = await self.evaluate_task_result(
                    task_id, agent_id, task_input, task_output, task_type
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to evaluate task {task_id}: {e}")
        
        return results
    
    def export_evaluation_report(
        self,
        filepath: str,
        time_period: str = "month"
    ):
        """評価レポートをエクスポート"""
        # 統計データを収集
        trends = self.analyze_quality_trends(time_period)
        recent_evaluations = self.get_evaluation_history(limit=100)
        
        # レポートデータを構成
        report = {
            "generated_at": datetime.now().isoformat(),
            "time_period": time_period,
            "overall_stats": self.evaluation_stats,
            "quality_trends": [asdict(trend) for trend in trends],
            "recent_evaluations": [asdict(eval_result) for eval_result in recent_evaluations[:20]],
            "summary": {
                "total_evaluations": len(recent_evaluations),
                "average_score": sum(e.overall_score for e in recent_evaluations) / len(recent_evaluations) if recent_evaluations else 0,
                "grade_distribution": self._calculate_grade_distribution(recent_evaluations)
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Evaluation report exported to {filepath}")
    
    def _calculate_grade_distribution(self, evaluations: List[EvaluationResult]) -> Dict[str, int]:
        """グレード分布を計算"""
        grades = defaultdict(int)
        for evaluation in evaluations:
            grades[evaluation.grade] += 1
        return dict(grades)
    
    def get_statistics(self) -> Dict[str, Any]:
        """評価統計を取得"""
        return {
            "evaluation_stats": self.evaluation_stats,
            "template_count": len(self.templates),
            "available_task_types": list(self.templates.keys())
        }