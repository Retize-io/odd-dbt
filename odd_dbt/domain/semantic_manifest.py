from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, List, Optional

from odd_dbt.utils import load_json


@dataclass
class NodeRelation:
    alias: str
    schema_name: str
    database: str
    relation_name: str


@dataclass
class MetricTypeParams:
    measure: Optional[Dict[str, str]] = None
    numerator: Optional[str] = None
    denominator: Optional[str] = None
    expr: Optional[str] = None
    window: Optional[str] = None
    grain_to_date: Optional[str] = None
    metrics: List[str] = field(default_factory=list)
    input_measures: List[str] = field(default_factory=list)


@dataclass
class Metric:
    name: str
    description: str
    type: str
    type_params: MetricTypeParams
    filter: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Metric":
        type_params_data = data.get("type_params", {})
        type_params = MetricTypeParams(
            measure=type_params_data.get("measure"),
            numerator=type_params_data.get("numerator"),
            denominator=type_params_data.get("denominator"),
            expr=type_params_data.get("expr"),
            window=type_params_data.get("window"),
            grain_to_date=type_params_data.get("grain_to_date"),
            metrics=type_params_data.get("metrics", []),
            input_measures=type_params_data.get("input_measures", []),
        )

        return cls(
            name=data["name"],
            description=data.get("description", ""),
            type=data["type"],
            type_params=type_params,
            filter=data.get("filter"),
            metadata=data.get("metadata"),
        )


@dataclass
class SavedQueryExport:
    name: str
    config: Dict[str, Any]


@dataclass
class SavedQuery:
    name: str
    query_params: Dict[str, Any]
    description: str
    metadata: Optional[Dict[str, Any]] = None
    label: Optional[str] = None
    exports: List[SavedQueryExport] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SavedQuery":
        exports = []
        for export_data in data.get("exports", []):
            exports.append(
                SavedQueryExport(
                    name=export_data["name"], config=export_data.get("config", {})
                )
            )

        return cls(
            name=data["name"],
            query_params=data.get("query_params", {}),
            description=data.get("description", ""),
            metadata=data.get("metadata"),
            label=data.get("label"),
            exports=exports,
        )


@dataclass
class SemanticModel:
    name: str
    description: str
    node_relation: NodeRelation
    entities: List[str]
    measures: List[str]
    dimensions: List[str]
    metrics: List[Metric] = field(default_factory=list)
    saved_queries: List[SavedQuery] = field(default_factory=list)
    defaults: Optional[Dict[str, Any]] = None
    project_configuration: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticModel":
        node_relation_data = data.get("node_relation", {})
        node_relation = NodeRelation(
            alias=node_relation_data.get("alias", ""),
            schema_name=node_relation_data.get("schema_name", ""),
            database=node_relation_data.get("database", ""),
            relation_name=node_relation_data.get("relation_name", ""),
        )

        metrics = []
        for metric_data in data.get("metrics", []):
            metrics.append(Metric.from_dict(metric_data))

        saved_queries = []
        for query_data in data.get("saved_queries", []):
            saved_queries.append(SavedQuery.from_dict(query_data))

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            node_relation=node_relation,
            entities=data.get("entities", []),
            measures=data.get("measures", []),
            dimensions=data.get("dimensions", []),
            metrics=metrics,
            saved_queries=saved_queries,
            defaults=data.get("defaults"),
            project_configuration=data.get("project_configuration"),
        )


class SemanticManifest:
    def __init__(self, file: Path) -> None:
        if file.exists():
            self._manifest = load_json(file)
        else:
            self._manifest = {"semantic_models": []}

    @cached_property
    def semantic_models(self) -> List[SemanticModel]:
        models = []
        for model_data in self._manifest.get("semantic_models", []):
            models.append(SemanticModel.from_dict(model_data))
        return models

    def get_metrics(self) -> List[Metric]:
        """Extract all metrics from all semantic models"""
        metrics = []
        for model in self.semantic_models:
            metrics.extend(model.metrics)
        return metrics
