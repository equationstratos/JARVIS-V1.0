"""
Observability — Traçage et métriques OpenTelemetry

Fournit:
- Traçage des appels agent
- Métriques de latence par agent/modèle
- Métriques de token usage
- Métriques de cache hit rate
- Métriques système (CPU, mémoire)
"""
from typing import Dict, Optional, Any
import time
from datetime import datetime
from dataclasses import dataclass, asdict

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


@dataclass
class MetricSnapshot:
    """Snapshot de métriques pour une exécution"""
    timestamp: str
    agent_name: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    tools_used: int
    confidence_score: float
    cache_hit: bool
    validation_passed: bool


class ObservabilityManager:
    """Gère la traçage et les métriques"""

    def __init__(self, enabled: bool = False, otlp_endpoint: Optional[str] = None):
        self.enabled = enabled and OTEL_AVAILABLE
        self.otlp_endpoint = otlp_endpoint or "http://localhost:4317"
        self.tracer = None
        self.meter = None
        self.metrics_history: list[MetricSnapshot] = []

        if self.enabled:
            self._initialize_otel()

    def _initialize_otel(self):
        """Initialise OpenTelemetry"""
        try:
            # Tracer
            otlp_exporter = OTLPSpanExporter(endpoint=self.otlp_endpoint)
            trace_provider = TracerProvider()
            trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            trace.set_tracer_provider(trace_provider)
            self.tracer = trace.get_tracer(__name__)

            # Metrics
            metrics_exporter = OTLPMetricExporter(endpoint=self.otlp_endpoint)
            metric_reader = PeriodicExportingMetricReader(metrics_exporter)
            meter_provider = MeterProvider(metric_readers=[metric_reader])
            metrics.set_meter_provider(meter_provider)
            self.meter = metrics.get_meter(__name__)

            print(f"✓ OpenTelemetry initialized ({self.otlp_endpoint})")
        except Exception as e:
            print(f"⚠ OpenTelemetry initialization failed: {e}")
            self.enabled = False

    def record_agent_execution(
        self,
        agent_name: str,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        tools_used: int = 0,
        confidence_score: float = 1.0,
        cache_hit: bool = False,
        validation_passed: bool = True,
    ) -> MetricSnapshot:
        """Enregistre l'exécution d'un agent"""
        snapshot = MetricSnapshot(
            timestamp=datetime.now().isoformat(),
            agent_name=agent_name,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            tools_used=tools_used,
            confidence_score=confidence_score,
            cache_hit=cache_hit,
            validation_passed=validation_passed,
        )

        # Ajouter à l'historique
        self.metrics_history.append(snapshot)

        # Record dans OpenTelemetry si disponible
        if self.enabled and self.meter:
            try:
                # Latency histogram
                latency_histogram = self.meter.create_histogram(
                    "agent.latency_ms",
                    description="Agent execution latency",
                    unit="ms",
                )
                latency_histogram.record(latency_ms, {"agent": agent_name, "model": model_name})

                # Token counter
                token_counter = self.meter.create_counter(
                    "agent.tokens_generated",
                    description="Total tokens generated",
                    unit="1",
                )
                token_counter.add(completion_tokens, {"agent": agent_name, "model": model_name})

                # Cache hit rate
                cache_counter = self.meter.create_counter(
                    "cache.hits",
                    description="Cache hits",
                    unit="1",
                )
                if cache_hit:
                    cache_counter.add(1, {"agent": agent_name})
            except Exception as e:
                print(f"⚠ Metric recording failed: {e}")

        return snapshot

    def get_agent_stats(self, agent_name: str) -> Dict[str, Any]:
        """Récupère les statistiques pour un agent"""
        agent_metrics = [m for m in self.metrics_history if m.agent_name == agent_name]

        if not agent_metrics:
            return {}

        latencies = [m.latency_ms for m in agent_metrics]
        total_tokens = sum(m.total_tokens for m in agent_metrics)
        cache_hits = sum(1 for m in agent_metrics if m.cache_hit)
        validation_passed = sum(1 for m in agent_metrics if m.validation_passed)

        return {
            "call_count": len(agent_metrics),
            "total_executions": len(agent_metrics),
            "avg_latency_ms": sum(latencies) / len(latencies),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "p95_latency_ms": sorted(latencies)[int(0.95 * len(latencies))],
            "total_tokens": total_tokens,
            "avg_tokens_per_call": total_tokens / len(agent_metrics),
            "cache_hit_rate": cache_hits / len(agent_metrics),
            "validation_pass_rate": validation_passed / len(agent_metrics),
            "avg_confidence": sum(m.confidence_score for m in agent_metrics) / len(agent_metrics),
        }

    def get_agent_info(self) -> Dict[str, str]:
        """Retourne les noms des agents avec des métriques"""
        return {name: name for name in set(m.agent_name for m in self.metrics_history)}

    def get_system_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques système (CPU, mémoire)"""
        stats = {}
        if PSUTIL_AVAILABLE:
            try:
                stats["cpu_percent"] = psutil.cpu_percent(interval=0.1)
                stats["memory_percent"] = psutil.virtual_memory().percent
                stats["memory_mb"] = psutil.virtual_memory().used / (1024 * 1024)
                stats["memory_total_mb"] = psutil.virtual_memory().total / (1024 * 1024)
            except Exception as e:
                pass
        return stats

    def get_global_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques globales"""
        stats = {
            "total_executions": 0,
            "avg_latency_ms": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "cache_hits": 0,
            "confidence_score": 0,
            "timestamp": datetime.now().isoformat(),
        }

        if not self.metrics_history:
            # Add system stats even if no metrics
            stats.update(self.get_system_stats())
            return stats

        all_metrics = self.metrics_history
        latencies = [m.latency_ms for m in all_metrics]
        total_tokens = sum(m.total_tokens for m in all_metrics)
        cache_hits = sum(1 for m in all_metrics if m.cache_hit)
        input_tokens = sum(m.prompt_tokens for m in all_metrics)
        output_tokens = sum(m.completion_tokens for m in all_metrics)

        stats.update({
            "total_executions": len(all_metrics),
            "avg_latency_ms": sum(latencies) / len(latencies),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "p50_latency_ms": sorted(latencies)[len(latencies) // 2],
            "p95_latency_ms": sorted(latencies)[int(0.95 * len(latencies))],
            "p99_latency_ms": sorted(latencies)[int(0.99 * len(latencies))],
            "total_tokens": total_tokens,
            "total_input_tokens": input_tokens,
            "total_output_tokens": output_tokens,
            "cache_hits": cache_hits,
            "cache_hit_rate": cache_hits / len(all_metrics),
            "avg_confidence": sum(m.confidence_score for m in all_metrics) / len(all_metrics),
            "confidence_score": sum(m.confidence_score for m in all_metrics) / len(all_metrics),
        })

        # Add system stats
        stats.update(self.get_system_stats())

        return stats

    def export_metrics(self, filepath: str) -> None:
        """Exporte les métriques en JSON"""
        import json

        data = {
            "global_stats": self.get_global_stats(),
            "agents": {
                agent_name: self.get_agent_stats(agent_name)
                for agent_name in set(m.agent_name for m in self.metrics_history)
            },
            "history": [asdict(m) for m in self.metrics_history[-100:]],  # Derniers 100
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        print(f"✓ Metrics exported to {filepath}")

    async def close(self):
        """Ferme la connexion OpenTelemetry"""
        if self.enabled and self.tracer:
            try:
                # Flush remaining spans
                pass
            except Exception as e:
                print(f"⚠ Error closing observability: {e}")
