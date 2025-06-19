#!/usr/bin/env python3
"""
LLM-as-judge評価システムの実装
"""

import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
import logging
from datetime import datetime
import statistics

logger = logging.getLogger(__name__)

class EvaluationCriteria(Enum):
    """評価基準"""
    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    CLARITY = "clarity"
    EFFICIENCY = "efficiency"
    CONSISTENCY = "consistency"
    CORRECTNESS = "correctness"
    CREATIVITY = "creativity"
    RELEVANCE = "relevance"
    SAFETY = "safety"

@dataclass
class CriteriaDefinition:
    """評価基準の定義"""
    criteria: EvaluationCriteria
    weight: float = 1.0
    description: str = ""
    scoring_guidelines: Dict[int, str] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.scoring_guidelines:
            self.scoring_guidelines = {
                5: "Excellent - Exceeds expectations",
                4: "Good - Meets expectations well",
                3: "Satisfactory - Meets basic expectations",
                2: "Below Average - Needs improvement",
                1: "Poor - Significantly below expectations"
            }

@dataclass
class EvaluationScore:
    """個別の評価スコア"""
    criteria: EvaluationCriteria
    score: float  # 1-5
    reasoning: str
    evidence: List[str] = field(default_factory=list)
    confidence: float = 1.0  # 0-1

@dataclass
class EvaluationResult:
    """評価結果"""
    evaluation_id: str
    task_id: str
    agent_id: str
    overall_score: float
    scores: List[EvaluationScore]
    suggestions: List[str]
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['scores'] = [
            {
                'criteria': score.criteria.value,
                'score': score.score,
                'reasoning': score.reasoning,
                'evidence': score.evidence,
                'confidence': score.confidence
            }
            for score in self.scores
        ]
        return data

@dataclass
class EvaluationTemplate:
    """評価テンプレート"""
    name: str
    description: str
    criteria: List[CriteriaDefinition]
    task_types: List[str] = field(default_factory=list)
    
    def get_total_weight(self) -> float:
        """総重みを取得"""
        return sum(c.weight for c in self.criteria)

class LLMJudgeEvaluator:
    """LLM-as-judge評価システム"""
    
    def __init__(self, judge_model: Optional[str] = None):
        self.judge_model = judge_model or "claude-3-opus"
        self.evaluation_history: List[EvaluationResult] = []
        self.templates: Dict[str, EvaluationTemplate] = {}
        self._init_default_templates()
        
        # 評価プロンプトのキャッシュ
        self.prompt_cache: Dict[str, str] = {}
        
    def _init_default_templates(self):
        """デフォルトの評価テンプレートを初期化"""
        # コードレビュー用テンプレート
        self.templates["code_review"] = EvaluationTemplate(
            name="code_review",
            description="Code review quality evaluation",
            criteria=[
                CriteriaDefinition(
                    criteria=EvaluationCriteria.ACCURACY,
                    weight=2.0,
                    description="Correctness of identified issues"
                ),
                CriteriaDefinition(
                    criteria=EvaluationCriteria.COMPLETENESS,
                    weight=1.5,
                    description="Coverage of all important aspects"
                ),
                CriteriaDefinition(
                    criteria=EvaluationCriteria.CLARITY,
                    weight=1.0,
                    description="Clarity of explanations"
                ),
                CriteriaDefinition(
                    criteria=EvaluationCriteria.RELEVANCE,
                    weight=1.5,
                    description="Relevance of suggestions"
                )
            ],
            task_types=["code_review"]
        )
        
        # リファクタリング用テンプレート
        self.templates["refactor"] = EvaluationTemplate(
            name="refactor",
            description="Refactoring quality evaluation",
            criteria=[
                CriteriaDefinition(
                    criteria=EvaluationCriteria.CORRECTNESS,
                    weight=2.0,
                    description="Preservation of functionality"
                ),
                CriteriaDefinition(
                    criteria=EvaluationCriteria.EFFICIENCY,
                    weight=1.5,
                    description="Performance improvements"
                ),
                CriteriaDefinition(
                    criteria=EvaluationCriteria.CLARITY,
                    weight=1.5,
                    description="Code readability improvements"
                ),
                CriteriaDefinition(
                    criteria=EvaluationCriteria.CONSISTENCY,
                    weight=1.0,
                    description="Consistency with coding standards"
                )
            ],
            task_types=["refactor"]
        )
        
        # 汎用テンプレート
        self.templates["generic"] = EvaluationTemplate(
            name="generic",
            description="Generic task evaluation",
            criteria=[
                CriteriaDefinition(
                    criteria=EvaluationCriteria.ACCURACY,
                    weight=1.0
                ),
                CriteriaDefinition(
                    criteria=EvaluationCriteria.COMPLETENESS,
                    weight=1.0
                ),
                CriteriaDefinition(
                    criteria=EvaluationCriteria.CLARITY,
                    weight=1.0
                )
            ],
            task_types=["generic", "analysis", "test_generation"]
        )
        
    async def evaluate_task_result(
        self,
        task_id: str,
        agent_id: str,
        task_input: Dict[str, Any],
        task_output: Dict[str, Any],
        task_type: str = "generic",
        custom_criteria: Optional[List[CriteriaDefinition]] = None
    ) -> EvaluationResult:
        """タスク結果を評価"""
        # 評価テンプレートを選択
        template = self._select_template(task_type)
        criteria = custom_criteria or template.criteria
        
        # 評価IDを生成
        evaluation_id = f"eval_{task_id}_{int(time.time() * 1000)}"
        
        # 各基準で評価
        scores = []
        for criterion in criteria:
            score = await self._evaluate_criterion(
                criterion,
                task_input,
                task_output,
                task_type
            )
            scores.append(score)
            
        # 総合スコアを計算
        total_weight = sum(c.weight for c in criteria)
        weighted_sum = sum(
            score.score * criterion.weight 
            for score, criterion in zip(scores, criteria)
        )
        overall_score = weighted_sum / total_weight if total_weight > 0 else 0
        
        # 改善提案を生成
        suggestions = await self._generate_suggestions(
            scores,
            task_input,
            task_output
        )
        
        # 評価結果を作成
        result = EvaluationResult(
            evaluation_id=evaluation_id,
            task_id=task_id,
            agent_id=agent_id,
            overall_score=overall_score,
            scores=scores,
            suggestions=suggestions,
            metadata={
                "task_type": task_type,
                "template_used": template.name,
                "criteria_count": len(criteria)
            }
        )
        
        # 履歴に追加
        self.evaluation_history.append(result)
        
        logger.info(
            f"Evaluation completed for task {task_id}: "
            f"Overall score {overall_score:.2f}/5.0"
        )
        
        return result
        
    async def _evaluate_criterion(
        self,
        criterion: CriteriaDefinition,
        task_input: Dict[str, Any],
        task_output: Dict[str, Any],
        task_type: str
    ) -> EvaluationScore:
        """個別の基準で評価"""
        # 評価プロンプトを生成
        prompt = self._create_evaluation_prompt(
            criterion,
            task_input,
            task_output,
            task_type
        )
        
        # LLMによる評価を実行（シミュレーション）
        # 実際の実装では、ここでLLM APIを呼び出す
        evaluation_response = await self._call_judge_llm(prompt)
        
        # レスポンスを解析
        score_value = evaluation_response.get("score", 3.0)
        reasoning = evaluation_response.get("reasoning", "")
        evidence = evaluation_response.get("evidence", [])
        confidence = evaluation_response.get("confidence", 0.8)
        
        return EvaluationScore(
            criteria=criterion.criteria,
            score=score_value,
            reasoning=reasoning,
            evidence=evidence,
            confidence=confidence
        )
        
    def _create_evaluation_prompt(
        self,
        criterion: CriteriaDefinition,
        task_input: Dict[str, Any],
        task_output: Dict[str, Any],
        task_type: str
    ) -> str:
        """評価プロンプトを作成"""
        # キャッシュキーを生成
        cache_key = f"{criterion.criteria.value}_{task_type}"
        
        if cache_key in self.prompt_cache:
            base_prompt = self.prompt_cache[cache_key]
        else:
            base_prompt = f"""
You are evaluating the quality of an AI agent's output for a {task_type} task.

Evaluation Criterion: {criterion.criteria.value}
Description: {criterion.description}

Scoring Guidelines:
{json.dumps(criterion.scoring_guidelines, indent=2)}

Please evaluate the output based on this criterion and provide:
1. A score from 1-5
2. Detailed reasoning for your score
3. Specific evidence from the output supporting your evaluation
4. Your confidence level (0-1) in this evaluation

Task Input:
{{task_input}}

Agent Output:
{{task_output}}

Respond in JSON format:
{{
    "score": <1-5>,
    "reasoning": "<detailed explanation>",
    "evidence": ["<specific example 1>", "<specific example 2>", ...],
    "confidence": <0-1>
}}
"""
            self.prompt_cache[cache_key] = base_prompt
            
        # 実際のデータを挿入
        prompt = base_prompt.format(
            task_input=json.dumps(task_input, indent=2),
            task_output=json.dumps(task_output, indent=2)
        )
        
        return prompt
        
    async def _call_judge_llm(self, prompt: str) -> Dict[str, Any]:
        """評価用LLMを呼び出し（シミュレーション）"""
        # 実際の実装では、ここでLLM APIを呼び出す
        # 現在はシミュレーション結果を返す
        
        await asyncio.sleep(0.1)  # API呼び出しのシミュレーション
        
        # シミュレーション結果
        import random
        
        score = random.uniform(3.0, 5.0)
        confidence = random.uniform(0.7, 0.95)
        
        return {
            "score": round(score, 1),
            "reasoning": f"The output demonstrates good quality with score {score:.1f}",
            "evidence": [
                "Clear structure and organization",
                "Addresses main requirements",
                "Minor areas for improvement identified"
            ],
            "confidence": round(confidence, 2)
        }
        
    async def _generate_suggestions(
        self,
        scores: List[EvaluationScore],
        task_input: Dict[str, Any],
        task_output: Dict[str, Any]
    ) -> List[str]:
        """改善提案を生成"""
        suggestions = []
        
        # 低スコアの基準に基づいて提案を生成
        for score in scores:
            if score.score < 3.0:
                if score.criteria == EvaluationCriteria.ACCURACY:
                    suggestions.append(
                        "Improve accuracy by double-checking facts and calculations"
                    )
                elif score.criteria == EvaluationCriteria.COMPLETENESS:
                    suggestions.append(
                        "Ensure all aspects of the task are addressed comprehensively"
                    )
                elif score.criteria == EvaluationCriteria.CLARITY:
                    suggestions.append(
                        "Enhance clarity with better structure and explanations"
                    )
                elif score.criteria == EvaluationCriteria.EFFICIENCY:
                    suggestions.append(
                        "Optimize for better performance and resource usage"
                    )
                    
        # 一般的な改善提案
        avg_score = statistics.mean(s.score for s in scores)
        if avg_score < 4.0:
            suggestions.append(
                "Consider reviewing similar high-scoring examples for improvement ideas"
            )
            
        return suggestions
        
    def _select_template(self, task_type: str) -> EvaluationTemplate:
        """タスクタイプに基づいてテンプレートを選択"""
        # 直接マッチ
        if task_type in self.templates:
            return self.templates[task_type]
            
        # タスクタイプでマッチ
        for template in self.templates.values():
            if task_type in template.task_types:
                return template
                
        # デフォルト
        return self.templates["generic"]
        
    async def batch_evaluate(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[EvaluationResult]:
        """複数のタスクをバッチ評価"""
        evaluation_tasks = []
        
        for task in tasks:
            eval_task = self.evaluate_task_result(
                task_id=task["task_id"],
                agent_id=task["agent_id"],
                task_input=task["input"],
                task_output=task["output"],
                task_type=task.get("task_type", "generic")
            )
            evaluation_tasks.append(eval_task)
            
        # 並列実行
        results = await asyncio.gather(*evaluation_tasks)
        
        return results
        
    def get_agent_performance_summary(
        self,
        agent_id: str,
        time_window: Optional[float] = None
    ) -> Dict[str, Any]:
        """エージェントのパフォーマンスサマリーを取得"""
        # 時間窓でフィルタリング
        if time_window:
            cutoff_time = time.time() - time_window
            relevant_evaluations = [
                e for e in self.evaluation_history
                if e.agent_id == agent_id and e.timestamp >= cutoff_time
            ]
        else:
            relevant_evaluations = [
                e for e in self.evaluation_history
                if e.agent_id == agent_id
            ]
            
        if not relevant_evaluations:
            return {
                "agent_id": agent_id,
                "evaluation_count": 0,
                "average_score": 0,
                "score_trend": "no_data"
            }
            
        # 統計を計算
        scores = [e.overall_score for e in relevant_evaluations]
        avg_score = statistics.mean(scores)
        
        # スコアのトレンドを分析
        if len(scores) >= 3:
            recent_avg = statistics.mean(scores[-3:])
            older_avg = statistics.mean(scores[:-3]) if len(scores) > 3 else scores[0]
            if recent_avg > older_avg + 0.1:
                trend = "improving"
            elif recent_avg < older_avg - 0.1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
            
        # 基準別のスコア
        criteria_scores = {}
        for evaluation in relevant_evaluations:
            for score in evaluation.scores:
                criteria = score.criteria.value
                if criteria not in criteria_scores:
                    criteria_scores[criteria] = []
                criteria_scores[criteria].append(score.score)
                
        criteria_averages = {
            criteria: statistics.mean(scores)
            for criteria, scores in criteria_scores.items()
        }
        
        return {
            "agent_id": agent_id,
            "evaluation_count": len(relevant_evaluations),
            "average_score": round(avg_score, 2),
            "score_trend": trend,
            "criteria_scores": criteria_averages,
            "recent_evaluations": [
                {
                    "task_id": e.task_id,
                    "score": e.overall_score,
                    "timestamp": e.timestamp
                }
                for e in relevant_evaluations[-5:]
            ]
        }
        
    def export_evaluation_report(
        self,
        filepath: str,
        time_window: Optional[float] = None
    ):
        """評価レポートをエクスポート"""
        # 時間窓でフィルタリング
        if time_window:
            cutoff_time = time.time() - time_window
            evaluations = [
                e for e in self.evaluation_history
                if e.timestamp >= cutoff_time
            ]
        else:
            evaluations = self.evaluation_history
            
        # エージェント別の集計
        agent_summaries = {}
        for evaluation in evaluations:
            agent_id = evaluation.agent_id
            if agent_id not in agent_summaries:
                agent_summaries[agent_id] = self.get_agent_performance_summary(
                    agent_id,
                    time_window
                )
                
        # タスクタイプ別の集計
        task_type_scores = {}
        for evaluation in evaluations:
            task_type = evaluation.metadata.get("task_type", "unknown")
            if task_type not in task_type_scores:
                task_type_scores[task_type] = []
            task_type_scores[task_type].append(evaluation.overall_score)
            
        task_type_averages = {
            task_type: statistics.mean(scores)
            for task_type, scores in task_type_scores.items()
        }
        
        # レポートを作成
        report = {
            "generated_at": datetime.now().isoformat(),
            "evaluation_count": len(evaluations),
            "time_window": time_window,
            "overall_average_score": statistics.mean(
                [e.overall_score for e in evaluations]
            ) if evaluations else 0,
            "agent_summaries": agent_summaries,
            "task_type_averages": task_type_averages,
            "top_performers": sorted(
                agent_summaries.items(),
                key=lambda x: x[1]["average_score"],
                reverse=True
            )[:5],
            "recent_evaluations": [
                e.to_dict() for e in sorted(
                    evaluations,
                    key=lambda x: x.timestamp,
                    reverse=True
                )[:10]
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Evaluation report exported to {filepath}")
        
    def add_custom_template(
        self,
        name: str,
        description: str,
        criteria: List[CriteriaDefinition],
        task_types: List[str]
    ):
        """カスタム評価テンプレートを追加"""
        template = EvaluationTemplate(
            name=name,
            description=description,
            criteria=criteria,
            task_types=task_types
        )
        
        self.templates[name] = template
        logger.info(f"Added custom evaluation template: {name}")
        
    async def continuous_improvement_loop(
        self,
        agent_id: str,
        improvement_callback: Callable[[Dict[str, Any]], None]
    ):
        """継続的改善ループ"""
        while True:
            # エージェントのパフォーマンスを分析
            summary = self.get_agent_performance_summary(
                agent_id,
                time_window=86400  # 24時間
            )
            
            # 改善が必要な領域を特定
            if summary["average_score"] < 4.0:
                improvement_areas = []
                
                for criteria, score in summary["criteria_scores"].items():
                    if score < 3.5:
                        improvement_areas.append({
                            "criteria": criteria,
                            "current_score": score,
                            "target_score": 4.0
                        })
                        
                if improvement_areas:
                    improvement_data = {
                        "agent_id": agent_id,
                        "current_performance": summary,
                        "improvement_areas": improvement_areas,
                        "timestamp": time.time()
                    }
                    
                    # コールバックを呼び出し
                    improvement_callback(improvement_data)
                    
            # 1時間待機
            await asyncio.sleep(3600)