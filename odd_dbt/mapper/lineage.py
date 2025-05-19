import traceback
from typing import Optional, Union

from dbt.contracts.graph.nodes import (
    ColumnInfo,
    ModelNode,
    SeedNode,
)
from dbt.contracts.graph.nodes import (
    Metric as MetricNode,
)
from dbt.contracts.graph.nodes import (
    SemanticModel as SemanticModelNode,
)
from odd_models import DataSetFieldType
from odd_models.models import (
    DataEntityList,
    DataEntityType,
    MetadataExtension,
    Type,
)
from oddrn_generator import DbtGenerator

from odd_dbt import logger
from odd_dbt.domain.context import DbtContext
from odd_dbt.domain.model import (
    ColumnEntity,
    MetricEntity,
    ModelEntity,
    NodeEntity,
    SeedEntity,
    SemanticModelEntity,
)
from odd_dbt.domain.semantic_manifest import Metric, SemanticModel
from odd_dbt.domain.source import Source
from odd_dbt.mapper.generator import create_generator
from odd_dbt.mapper.metadata import get_model_metadata
from odd_dbt.mapper.types import DBT_TO_ODD


class DbtLineageMapper:
    _SUPPORTED_NODE_TYPES = (ModelNode, SeedNode, MetricNode, SemanticModelNode)

    def __init__(self, context: DbtContext, generator: DbtGenerator) -> None:
        self._context = context
        self._generator = generator
        self._nodes = {
            uid: node
            for uid, node in self._context.manifest.nodes.items()
            if isinstance(node, self._SUPPORTED_NODE_TYPES)
        }
        self._sources = self._context.manifest.sources
        self._metrics = self._context.manifest.metrics

        # Load semantic models and metrics from semantic_manifest.json if available
        try:
            self._semantic_models = self._context.semantic_manifest.semantic_models
            self._semantic_metrics = self._context.semantic_manifest.get_metrics()
        except Exception as e:
            logger.warning(f"Error loading semantic manifest: {str(e)}")
            self._semantic_models = []
            self._semantic_metrics = []

    def map(self) -> DataEntityList:
        nodes: dict[str, Union[ModelNode, SeedNode, MetricNode, SemanticModelNode]] = (
            self._nodes
        )

        node_entities = {}
        # Map regular dbt nodes
        for uid, node in nodes.items():
            try:
                node_entities[uid] = self.map_node(node)
            except Exception as e:
                logger.warning(f"Can't map node {node.unique_id}: {str(e)}")
                logger.debug(traceback.format_exc())
                continue

        # Map metrics from manifest.json
        metric_entities = {}
        for uid, metric in self._metrics.items():
            try:
                metric_entities[uid] = self.map_metric(metric)
            except Exception as e:
                logger.warning(f"Can't map metric {metric.unique_id}: {str(e)}")
                logger.debug(traceback.format_exc())
                continue

        # Map semantic models and metrics from semantic_manifest.json
        semantic_model_entities = {}
        semantic_metric_entities = {}

        for semantic_model in self._semantic_models:
            try:
                model_entity = self.map_semantic_model(semantic_model)
                if model_entity:
                    semantic_model_entities[semantic_model.name] = model_entity
            except Exception as e:
                logger.warning(
                    f"Can't map semantic model {semantic_model.name}: {str(e)}"
                )
                logger.debug(traceback.format_exc())
                continue

        for metric in self._semantic_metrics:
            try:
                metric_entity = self.map_semantic_metric(metric)
                if metric_entity:
                    semantic_metric_entities[metric.name] = metric_entity
            except Exception as e:
                logger.warning(f"Can't map semantic metric {metric.name}: {str(e)}")
                logger.debug(traceback.format_exc())
                continue

        # Process dependencies for regular nodes
        for node_id, entity in node_entities.items():
            upstream_ids = nodes[node_id].depends_on_nodes

            for upstream_id in upstream_ids:
                if source := self._sources.get(upstream_id):
                    entity.add_input(get_source_oddrn(source, self._context))
                    continue

                upstream_entity = node_entities.get(upstream_id)

                if not upstream_entity:
                    logger.warning(
                        f"For {node_id} Can't find node {upstream_id}. Upstream node must be model, seed, metric, or semantic model"
                    )
                    continue

                entity.add_upstream(upstream_entity)

        # Connect metrics to their source models
        for metric_id, metric in self._metrics.items():
            metric_entity = metric_entities.get(metric_id)
            if not metric_entity:
                continue

            # Connect to models mentioned in depends_on_nodes
            for upstream_id in metric.depends_on_nodes:
                upstream_entity = node_entities.get(upstream_id)
                if upstream_entity:
                    metric_entity.add_upstream(upstream_entity)

        # Connect semantic metrics to their semantic models
        for semantic_model in self._semantic_models:
            model_entity = semantic_model_entities.get(semantic_model.name)
            if not model_entity:
                continue

            # For each metric in the semantic model, add the model as an upstream
            for metric in semantic_model.metrics:
                metric_entity = semantic_metric_entities.get(metric.name)
                if metric_entity:
                    metric_entity.add_upstream(model_entity)

                    # If the metric has dependencies on other metrics, connect them
                    for ref_metric_name in metric.type_params.metrics:
                        ref_metric_entity = semantic_metric_entities.get(
                            ref_metric_name
                        )
                        if ref_metric_entity:
                            metric_entity.add_upstream(ref_metric_entity)

        # Combine all entities
        all_entities = list(node_entities.values())
        all_entities.extend(list(metric_entities.values()))
        all_entities.extend(list(semantic_model_entities.values()))
        all_entities.extend(list(semantic_metric_entities.values()))

        return DataEntityList(
            data_source_oddrn=self._generator.get_data_source_oddrn(),
            items=all_entities,
        )

    def map_node(
        self, node: Union[ModelNode, SeedNode, MetricNode, SemanticModelNode]
    ) -> Optional[NodeEntity]:
        if isinstance(node, ModelNode):
            return self.map_model(node)
        elif isinstance(node, SeedNode):
            return self.map_seed(node)
        elif isinstance(node, MetricNode):
            return self.map_metric(node)
        elif isinstance(node, SemanticModelNode):
            return self.map_semantic_model_node(node)
        return None

    def map_model(self, model: ModelNode) -> ModelEntity:
        metadata = get_model_metadata(model)

        # Check if any columns are missing types and add a warning metadata
        missing_types = [
            col_name for col_name, col in model.columns.items() if not col.data_type
        ]
        if missing_types:
            missing_types_metadata = {
                "warning": "Missing column types",
                "affected_columns": missing_types,
                "recommendation": "Add data_type in schema.yml for better type information",
            }
            schema_url = "https://raw.githubusercontent.com/opendatadiscovery/opendatadiscovery-specification/main/specification/extensions/dbt.json#/definitions/ColumnWarning"
            metadata.append(
                MetadataExtension(
                    schema_url=schema_url, metadata=missing_types_metadata
                )
            )

        entity = ModelEntity(
            oddrn=self._generator.get_oddrn_for(model),
            name=model.name,
            type=DataEntityType.TABLE
            if model.config.materialized != "view"
            else DataEntityType.VIEW,
            metadata=metadata,
        )

        for column_name, column in model.columns.items():
            entity_column = self.map_column(column, column_name, model)
            entity.dataset.field_list.append(entity_column)

        return entity

    def map_seed(self, seed: SeedNode) -> SeedEntity:
        entity = SeedEntity(
            oddrn=self._generator.get_oddrn_for(seed),
            name=seed.name,
            type=DataEntityType.TABLE,
            metadata=get_model_metadata(seed),
        )

        for column_name, column in seed.columns.items():
            entity_column = self.map_column(column, column_name, seed)
            entity.dataset.field_list.append(entity_column)

        return entity

    def map_metric(self, metric: MetricNode) -> MetricEntity:
        """Map a metric from the manifest.json file"""
        from odd_dbt.mapper.metadata import get_metric_metadata

        entity = MetricEntity(
            oddrn=self._generator.get_oddrn_for(metric),
            name=metric.name,
            type=DataEntityType.METRIC,
            metadata=get_metric_metadata(metric),
        )

        return entity

    def map_semantic_model_node(
        self, semantic_model: SemanticModelNode
    ) -> SemanticModelEntity:
        """Map a semantic model from the manifest.json file"""
        from odd_dbt.mapper.metadata import get_semantic_model_metadata

        entity = SemanticModelEntity(
            oddrn=self._generator.get_oddrn_for(semantic_model),
            name=semantic_model.name,
            type=DataEntityType.ENTITY,  # Using ENTITY as the type for semantic models
            metadata=get_semantic_model_metadata(semantic_model),
        )

        return entity

    def map_semantic_model(self, semantic_model: SemanticModel) -> SemanticModelEntity:
        """Map a semantic model from the semantic_manifest.json file"""
        from odd_dbt.mapper.metadata import get_semantic_manifest_model_metadata

        entity = SemanticModelEntity(
            oddrn=self._generator.get_oddrn_for(semantic_model),
            name=semantic_model.name,
            type=DataEntityType.ENTITY,  # Using ENTITY as the type for semantic models
            metadata=get_semantic_manifest_model_metadata(semantic_model),
        )

        return entity

    def map_semantic_metric(self, metric: Metric) -> MetricEntity:
        """Map a metric from the semantic_manifest.json file"""
        from odd_dbt.mapper.metadata import get_semantic_metric_metadata

        entity = MetricEntity(
            oddrn=self._generator.get_oddrn_for(metric),
            name=metric.name,
            type=DataEntityType.METRIC,
            metadata=get_semantic_metric_metadata(metric),
        )

        return entity

    def map_column(
        self,
        column: ColumnInfo,
        column_name: str,
        parent_node: Union[ModelNode, SeedNode],
    ) -> ColumnEntity:
        """Map a column from a dbt model or seed to an ODD column entity"""
        # Default to STRING type if no type is specified
        type_enum = DBT_TO_ODD.get(
            (column.data_type or "STRING").upper(), Type.TYPE_STRING
        )
        type_mapping = DataSetFieldType(
            type=type_enum,
            is_nullable=True,  # Default to nullable since DBT doesn't specify this
        )

        entity = ColumnEntity(
            name=column_name,
            oddrn=f"{self._generator.get_oddrn_for(parent_node)}/columns/{column_name}",
            type=type_mapping,
            description=column.description or "",
        )

        return entity


def get_source_oddrn(source_node: Source, context: DbtContext) -> str:
    return create_generator(
        adapter_type=context.adapter_type,
        credentials=context.credentials,
    ).get_oddrn_for(source_node)


def get_materialized_entity_oddrn(model_node: ModelNode, context: DbtContext) -> str:
    return create_generator(
        adapter_type=context.adapter_type,
        credentials=context.credentials,
    ).get_oddrn_for(model_node)
