from functools import cached_property
from pathlib import Path

from dbt.contracts.graph.nodes import (
    GenericTestNode,
    ModelNode,
    ParsedNode,
    SeedNode,
)
from dbt.contracts.graph.nodes import (
    Metric as MetricNode,
)
from dbt.contracts.graph.nodes import (
    SemanticModel as SemanticModelNode,
)
from funcy import select_values, walk_values

from odd_dbt.domain.source import Source
from odd_dbt.utils import load_json


class Manifest:
    def __init__(self, file: Path) -> None:
        self._manifest = load_json(file)

    @cached_property
    def nodes(self) -> dict[str, ParsedNode]:
        return walk_values(ParsedNode._deserialize, self._manifest["nodes"])

    @cached_property
    def sources(self) -> dict[str, Source]:
        return walk_values(Source._deserialize, self._manifest["sources"])

    @cached_property
    def generic_tests(self) -> dict[str, GenericTestNode]:
        return select_values(lambda x: isinstance(x, GenericTestNode), self.nodes)

    @cached_property
    def models(self) -> dict[str, ModelNode]:
        return select_values(lambda x: isinstance(x, ModelNode), self.nodes)

    @cached_property
    def seeds(self) -> dict[str, SeedNode]:
        return select_values(lambda x: isinstance(x, SeedNode), self.nodes)

    @cached_property
    def metrics(self) -> dict[str, MetricNode]:
        if "metrics" in self._manifest:
            # MetricNode doesn't have _deserialize, so create objects directly
            metrics = {}
            for key, value in self._manifest["metrics"].items():
                try:
                    if hasattr(MetricNode, "from_dict"):
                        metrics[key] = MetricNode.from_dict(value)
                    else:
                        metrics[key] = MetricNode(**value)
                except Exception as e:
                    from odd_dbt import logger

                    logger.warning(f"Failed to parse metric {key}: {str(e)}")
            return metrics
        return {}

    @cached_property
    def semantic_models(self) -> dict[str, SemanticModelNode]:
        semantic_model_nodes = select_values(
            lambda x: isinstance(x, SemanticModelNode), self.nodes
        )
        return semantic_model_nodes
