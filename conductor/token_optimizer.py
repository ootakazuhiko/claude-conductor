#!/usr/bin/env python3
"""
トークン使用量最適化とコスト分析機能
"""

import time
import json
import sqlite3
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime, timedelta
import logging
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)

class ModelType(Enum):
    """モデルタイプ"""
    CLAUDE_3_OPUS = "claude-3-opus"
    CLAUDE_3_SONNET = "claude-3-sonnet"
    CLAUDE_3_HAIKU = "claude-3-haiku"
    CLAUDE_2_1 = "claude-2.1"
    CLAUDE_2 = "claude-2"
    CLAUDE_INSTANT = "claude-instant"

@dataclass
class TokenUsage:
    """トークン使用量"""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: ModelType
    task_id: str
    agent_id: str
    timestamp: float = field(default_factory=time.time)
    
    @property
    def cost(self) -> float:
        """コストを計算"""
        return calculate_cost(self.input_tokens, self.output_tokens, self.model)

@dataclass
class CostAnalysis:
    """コスト分析結果"""
    total_cost: float
    input_cost: float
    output_cost: float
    cost_by_model: Dict[str, float]
    cost_by_agent: Dict[str, float]
    cost_by_task_type: Dict[str, float]
    time_period: str
    token_efficiency: float  # 出力トークン/入力トークン比
    
@dataclass
class OptimizationSuggestion:
    """最適化提案"""
    suggestion_type: str
    description: str
    potential_savings: float
    implementation_difficulty: str  # easy, medium, hard
    impact: str  # low, medium, high
    specific_actions: List[str]

# モデル別の料金設定（USD per 1K tokens）
MODEL_PRICING = {
    ModelType.CLAUDE_3_OPUS: {
        "input": 0.015,
        "output": 0.075
    },
    ModelType.CLAUDE_3_SONNET: {
        "input": 0.003,
        "output": 0.015
    },
    ModelType.CLAUDE_3_HAIKU: {
        "input": 0.00025,
        "output": 0.00125
    },
    ModelType.CLAUDE_2_1: {
        "input": 0.008,
        "output": 0.024
    },
    ModelType.CLAUDE_2: {
        "input": 0.008,
        "output": 0.024
    },
    ModelType.CLAUDE_INSTANT: {
        "input": 0.0008,
        "output": 0.0024
    }
}

def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model: ModelType
) -> float:
    """トークン使用量からコストを計算"""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING[ModelType.CLAUDE_3_SONNET])
    
    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    
    return input_cost + output_cost

class TokenOptimizer:
    """トークン使用量最適化エンジン"""
    
    def __init__(self, db_path: str = "/tmp/token_usage.db"):
        self.db_path = db_path
        self._init_db()
        
        # 最適化戦略
        self.optimization_strategies = {
            "model_selection": self._optimize_model_selection,
            "prompt_compression": self._optimize_prompt_compression,
            "caching": self._optimize_caching,
            "batching": self._optimize_batching,
            "task_routing": self._optimize_task_routing
        }
        
    def _init_db(self):
        """データベースを初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                cost REAL NOT NULL,
                timestamp REAL NOT NULL,
                task_type TEXT,
                success BOOLEAN DEFAULT TRUE
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_id ON token_usage(task_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_id ON token_usage(agent_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON token_usage(timestamp)
        """)
        
        conn.commit()
        conn.close()
        
    def record_usage(
        self,
        usage: TokenUsage,
        task_type: Optional[str] = None,
        success: bool = True
    ):
        """トークン使用量を記録"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO token_usage (
                task_id, agent_id, model, input_tokens, output_tokens,
                total_tokens, cost, timestamp, task_type, success
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            usage.task_id,
            usage.agent_id,
            usage.model.value,
            usage.input_tokens,
            usage.output_tokens,
            usage.total_tokens,
            usage.cost,
            usage.timestamp,
            task_type,
            success
        ))
        
        conn.commit()
        conn.close()
        
        logger.debug(
            f"Recorded token usage: {usage.total_tokens} tokens, "
            f"${usage.cost:.4f} for task {usage.task_id}"
        )
        
    def analyze_costs(
        self,
        time_period: Optional[str] = "day",
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> CostAnalysis:
        """コストを分析"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 時間範囲を設定
        if not start_time:
            if time_period == "hour":
                start_time = time.time() - 3600
            elif time_period == "day":
                start_time = time.time() - 86400
            elif time_period == "week":
                start_time = time.time() - 604800
            elif time_period == "month":
                start_time = time.time() - 2592000
            else:
                start_time = 0
                
        if not end_time:
            end_time = time.time()
            
        # 総コストを計算
        cursor.execute("""
            SELECT 
                SUM(cost) as total_cost,
                SUM(input_tokens * cost / total_tokens) as input_cost,
                SUM(output_tokens * cost / total_tokens) as output_cost,
                SUM(input_tokens) as total_input,
                SUM(output_tokens) as total_output
            FROM token_usage
            WHERE timestamp >= ? AND timestamp <= ?
        """, (start_time, end_time))
        
        result = cursor.fetchone()
        total_cost = result[0] or 0
        input_cost = result[1] or 0
        output_cost = result[2] or 0
        total_input = result[3] or 1
        total_output = result[4] or 0
        
        # モデル別コスト
        cursor.execute("""
            SELECT model, SUM(cost) as model_cost
            FROM token_usage
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY model
        """, (start_time, end_time))
        
        cost_by_model = {row[0]: row[1] for row in cursor.fetchall()}
        
        # エージェント別コスト
        cursor.execute("""
            SELECT agent_id, SUM(cost) as agent_cost
            FROM token_usage
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY agent_id
        """, (start_time, end_time))
        
        cost_by_agent = {row[0]: row[1] for row in cursor.fetchall()}
        
        # タスクタイプ別コスト
        cursor.execute("""
            SELECT task_type, SUM(cost) as task_cost
            FROM token_usage
            WHERE timestamp >= ? AND timestamp <= ?
            AND task_type IS NOT NULL
            GROUP BY task_type
        """, (start_time, end_time))
        
        cost_by_task_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        
        return CostAnalysis(
            total_cost=total_cost,
            input_cost=input_cost,
            output_cost=output_cost,
            cost_by_model=cost_by_model,
            cost_by_agent=cost_by_agent,
            cost_by_task_type=cost_by_task_type,
            time_period=time_period,
            token_efficiency=total_output / total_input if total_input > 0 else 0
        )
        
    def get_optimization_suggestions(
        self,
        analysis_period: str = "week"
    ) -> List[OptimizationSuggestion]:
        """最適化提案を生成"""
        suggestions = []
        
        # 各戦略を実行
        for strategy_name, strategy_func in self.optimization_strategies.items():
            try:
                suggestion = strategy_func(analysis_period)
                if suggestion:
                    suggestions.append(suggestion)
            except Exception as e:
                logger.error(f"Optimization strategy {strategy_name} failed: {e}")
                
        # 影響度でソート
        impact_order = {"high": 3, "medium": 2, "low": 1}
        suggestions.sort(
            key=lambda s: (
                impact_order.get(s.impact, 0),
                s.potential_savings
            ),
            reverse=True
        )
        
        return suggestions
        
    def _optimize_model_selection(
        self,
        analysis_period: str
    ) -> Optional[OptimizationSuggestion]:
        """モデル選択の最適化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_time = time.time() - (86400 * 7)  # 1週間
        
        # タスクタイプ別のモデル使用状況を分析
        cursor.execute("""
            SELECT 
                task_type,
                model,
                AVG(total_tokens) as avg_tokens,
                AVG(cost) as avg_cost,
                COUNT(*) as task_count,
                AVG(CASE WHEN success THEN 1 ELSE 0 END) as success_rate
            FROM token_usage
            WHERE timestamp >= ?
            AND task_type IS NOT NULL
            GROUP BY task_type, model
            HAVING task_count > 10
        """, (start_time,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return None
            
        # タスクタイプごとに最適なモデルを特定
        task_recommendations = defaultdict(list)
        potential_savings = 0
        
        for task_type, model, avg_tokens, avg_cost, task_count, success_rate in results:
            # 簡単なタスクに高性能モデルを使用している場合
            if avg_tokens < 1000 and model in [
                ModelType.CLAUDE_3_OPUS.value,
                ModelType.CLAUDE_3_SONNET.value
            ]:
                # より安価なモデルでの推定コスト
                haiku_cost = calculate_cost(
                    int(avg_tokens * 0.4),  # 入力の推定
                    int(avg_tokens * 0.6),  # 出力の推定
                    ModelType.CLAUDE_3_HAIKU
                )
                
                savings = (avg_cost - haiku_cost) * task_count
                potential_savings += savings
                
                task_recommendations[task_type].append(
                    f"Use Claude 3 Haiku instead of {model} "
                    f"(saves ${savings:.2f} per week)"
                )
                
        if not task_recommendations:
            return None
            
        actions = []
        for task_type, recommendations in task_recommendations.items():
            actions.extend([
                f"{task_type}: {rec}" for rec in recommendations
            ])
            
        return OptimizationSuggestion(
            suggestion_type="model_selection",
            description="Optimize model selection based on task complexity",
            potential_savings=potential_savings,
            implementation_difficulty="easy",
            impact="high" if potential_savings > 100 else "medium",
            specific_actions=actions
        )
        
    def _optimize_prompt_compression(
        self,
        analysis_period: str
    ) -> Optional[OptimizationSuggestion]:
        """プロンプト圧縮の最適化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_time = time.time() - (86400 * 7)
        
        # 入力トークンが多いタスクを特定
        cursor.execute("""
            SELECT 
                task_type,
                AVG(input_tokens) as avg_input,
                AVG(output_tokens) as avg_output,
                COUNT(*) as count
            FROM token_usage
            WHERE timestamp >= ?
            AND task_type IS NOT NULL
            GROUP BY task_type
            HAVING avg_input > 2000
        """, (start_time,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return None
            
        actions = []
        total_savings = 0
        
        for task_type, avg_input, avg_output, count in results:
            # 20%の圧縮が可能と仮定
            compressed_input = avg_input * 0.8
            
            # 各モデルでの節約額を計算（仮定）
            savings_per_task = avg_input * 0.2 / 1000 * 0.003  # Sonnetの価格で計算
            weekly_savings = savings_per_task * count
            total_savings += weekly_savings
            
            actions.append(
                f"{task_type}: Compress prompts to reduce ~{int(avg_input * 0.2)} "
                f"tokens per request (saves ${weekly_savings:.2f}/week)"
            )
            
        if not actions:
            return None
            
        return OptimizationSuggestion(
            suggestion_type="prompt_compression",
            description="Reduce input tokens through prompt optimization",
            potential_savings=total_savings,
            implementation_difficulty="medium",
            impact="medium",
            specific_actions=actions
        )
        
    def _optimize_caching(
        self,
        analysis_period: str
    ) -> Optional[OptimizationSuggestion]:
        """キャッシングの最適化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_time = time.time() - (86400 * 7)
        
        # 類似タスクの重複を検出
        cursor.execute("""
            SELECT 
                task_type,
                COUNT(*) as total_count,
                COUNT(DISTINCT task_id) as unique_count,
                AVG(cost) as avg_cost
            FROM token_usage
            WHERE timestamp >= ?
            AND task_type IS NOT NULL
            GROUP BY task_type
            HAVING total_count > unique_count * 1.5
        """, (start_time,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return None
            
        actions = []
        total_savings = 0
        
        for task_type, total_count, unique_count, avg_cost in results:
            duplicate_ratio = (total_count - unique_count) / total_count
            potential_cache_hits = int(total_count * duplicate_ratio * 0.7)  # 70%キャッシュヒット率
            
            savings = potential_cache_hits * avg_cost
            total_savings += savings
            
            actions.append(
                f"{task_type}: Implement caching for {duplicate_ratio:.0%} "
                f"duplicate requests (saves ${savings:.2f}/week)"
            )
            
        if not actions:
            return None
            
        return OptimizationSuggestion(
            suggestion_type="caching",
            description="Implement result caching for duplicate requests",
            potential_savings=total_savings,
            implementation_difficulty="medium",
            impact="high" if total_savings > 50 else "medium",
            specific_actions=actions
        )
        
    def _optimize_batching(
        self,
        analysis_period: str
    ) -> Optional[OptimizationSuggestion]:
        """バッチ処理の最適化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_time = time.time() - (86400 * 7)
        
        # 短時間に集中しているタスクを検出
        cursor.execute("""
            SELECT 
                task_type,
                COUNT(*) as count,
                MIN(timestamp) as start_time,
                MAX(timestamp) as end_time,
                AVG(input_tokens) as avg_input
            FROM token_usage
            WHERE timestamp >= ?
            AND task_type IS NOT NULL
            GROUP BY task_type, CAST(timestamp / 300 AS INTEGER)
            HAVING count > 5
        """, (start_time,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return None
            
        actions = []
        total_savings = 0
        
        for task_type, count, start, end, avg_input in results:
            time_window = end - start
            if time_window < 300 and count > 5:  # 5分以内に5個以上
                # バッチ処理による節約（共通コンテキストの削減）
                savings_ratio = 0.3  # 30%の入力削減
                saved_tokens = avg_input * count * savings_ratio
                savings = saved_tokens / 1000 * 0.003  # Sonnet価格
                total_savings += savings
                
                actions.append(
                    f"{task_type}: Batch {count} requests within {int(time_window)}s "
                    f"windows (saves ${savings:.2f}/week)"
                )
                
        if not actions:
            return None
            
        return OptimizationSuggestion(
            suggestion_type="batching",
            description="Batch similar requests to reduce redundant context",
            potential_savings=total_savings,
            implementation_difficulty="hard",
            impact="medium",
            specific_actions=actions
        )
        
    def _optimize_task_routing(
        self,
        analysis_period: str
    ) -> Optional[OptimizationSuggestion]:
        """タスクルーティングの最適化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_time = time.time() - (86400 * 7)
        
        # エージェントごとの効率性を分析
        cursor.execute("""
            SELECT 
                agent_id,
                task_type,
                AVG(output_tokens / CAST(input_tokens AS FLOAT)) as efficiency,
                AVG(cost) as avg_cost,
                COUNT(*) as count,
                AVG(CASE WHEN success THEN 1 ELSE 0 END) as success_rate
            FROM token_usage
            WHERE timestamp >= ?
            AND task_type IS NOT NULL
            AND input_tokens > 0
            GROUP BY agent_id, task_type
            HAVING count > 10
        """, (start_time,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return None
            
        # タスクタイプごとの最適なエージェントを特定
        task_best_agents = defaultdict(lambda: {"agent": None, "efficiency": 0})
        
        for agent_id, task_type, efficiency, avg_cost, count, success_rate in results:
            if efficiency > task_best_agents[task_type]["efficiency"]:
                task_best_agents[task_type] = {
                    "agent": agent_id,
                    "efficiency": efficiency,
                    "cost": avg_cost,
                    "success_rate": success_rate
                }
                
        actions = []
        total_savings = 0
        
        # 非効率なルーティングを検出
        for agent_id, task_type, efficiency, avg_cost, count, success_rate in results:
            best = task_best_agents[task_type]
            if agent_id != best["agent"] and efficiency < best["efficiency"] * 0.8:
                savings = (avg_cost - best["cost"]) * count * 0.5  # 50%を再ルーティング
                if savings > 0:
                    total_savings += savings
                    actions.append(
                        f"Route more {task_type} tasks from {agent_id} to {best['agent']} "
                        f"(efficiency: {efficiency:.2f} vs {best['efficiency']:.2f}, "
                        f"saves ${savings:.2f}/week)"
                    )
                    
        if not actions:
            return None
            
        return OptimizationSuggestion(
            suggestion_type="task_routing",
            description="Optimize task routing based on agent efficiency",
            potential_savings=total_savings,
            implementation_difficulty="easy",
            impact="medium",
            specific_actions=actions[:5]  # 上位5つのみ
        )
        
    def predict_future_costs(
        self,
        days_ahead: int = 30
    ) -> Dict[str, Any]:
        """将来のコストを予測"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 過去30日間のデータを取得
        start_time = time.time() - (86400 * 30)
        
        cursor.execute("""
            SELECT 
                DATE(timestamp, 'unixepoch') as date,
                SUM(cost) as daily_cost,
                SUM(total_tokens) as daily_tokens
            FROM token_usage
            WHERE timestamp >= ?
            GROUP BY date
            ORDER BY date
        """, (start_time,))
        
        results = cursor.fetchall()
        conn.close()
        
        if len(results) < 7:
            return {
                "error": "Insufficient data for prediction",
                "required_days": 7,
                "available_days": len(results)
            }
            
        # 日次コストの配列を作成
        daily_costs = [row[1] for row in results]
        
        # 簡単な線形回帰で予測
        x = np.arange(len(daily_costs))
        y = np.array(daily_costs)
        
        # 係数を計算
        A = np.vstack([x, np.ones(len(x))]).T
        m, c = np.linalg.lstsq(A, y, rcond=None)[0]
        
        # 将来の予測
        future_x = np.arange(len(daily_costs), len(daily_costs) + days_ahead)
        future_costs = m * future_x + c
        
        # 予測結果
        total_predicted_cost = np.sum(future_costs)
        avg_daily_cost = np.mean(future_costs)
        
        # 信頼区間（簡易版）
        std_dev = np.std(daily_costs)
        confidence_interval = 1.96 * std_dev * np.sqrt(days_ahead)
        
        return {
            "predicted_total_cost": float(total_predicted_cost),
            "predicted_daily_average": float(avg_daily_cost),
            "confidence_interval": float(confidence_interval),
            "trend": "increasing" if m > 0 else "decreasing",
            "trend_rate": float(m),
            "days_ahead": days_ahead,
            "based_on_days": len(daily_costs)
        }
        
    def export_report(
        self,
        filepath: str,
        period: str = "month"
    ):
        """詳細レポートをエクスポート"""
        analysis = self.analyze_costs(period)
        suggestions = self.get_optimization_suggestions()
        prediction = self.predict_future_costs()
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "period": period,
            "cost_analysis": asdict(analysis),
            "optimization_suggestions": [
                asdict(s) for s in suggestions
            ],
            "future_prediction": prediction,
            "summary": {
                "total_cost": analysis.total_cost,
                "potential_savings": sum(s.potential_savings for s in suggestions),
                "top_recommendation": suggestions[0].description if suggestions else None
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Cost analysis report exported to {filepath}")