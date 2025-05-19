"""Tests for metrics and semantic models support."""

from unittest.mock import MagicMock

import pytest
from dbt.contracts.graph.nodes import MetricNode, ModelNode, SemanticModelNode
from odd_dbt.domain.context import DbtContext
from odd_dbt.domain.semantic_manifest import Metric, SemanticManifest, SemanticModel
from odd_dbt.mapper.generator import create_generator
from odd_dbt.mapper.lineage import DbtLineageMapper
from odd_models.models import DataEntityType


@pytest.fixture
def mock_context():
    """Create a mock context with metrics and semantic models."""
    context = MagicMock(spec=DbtContext)

    # Mock manifest with metrics and models
    manifest = MagicMock()

    # Mock metric
    metric = MagicMock(spec=MetricNode)
    metric.name = "test_metric"
    metric.description = "Test metric description"
    metric.depends_on_nodes = ["model.test.test_model"]
    metric.unique_id = "metric.test.test_metric"

    # Mock semantic model
    semantic_model = MagicMock(spec=SemanticModelNode)
    semantic_model.name = "test_semantic_model"
    semantic_model.description = "Test semantic model description"
    semantic_model.unique_id = "semantic_model.test.test_semantic_model"

    # Mock model
    model = MagicMock(spec=ModelNode)
    model.name = "test_model"
    model.schema = "public"
    model.depends_on_nodes = []
    model.unique_id = "model.test.test_model"
    model.columns = {}

    # Setup manifest mocks
    manifest.metrics = {"metric.test.test_metric": metric}
    manifest.nodes = {
        "model.test.test_model": model,
        "semantic_model.test.test_semantic_model": semantic_model,
    }
    manifest.sources = {}

    # Setup semantic manifest mocks
    semantic_manifest = MagicMock(spec=SemanticManifest)

    # Create a semantic model in the semantic manifest
    sm_model = MagicMock(spec=SemanticModel)
    sm_model.name = "semantic_test_model"
    sm_model.description = "Semantic test model description"
    node_relation = MagicMock()
    node_relation.database = "test_db"
    node_relation.schema_name = "analytics"
    node_relation.alias = "test_model_alias"
    node_relation.relation_name = "test_db.analytics.test_model_alias"
    sm_model.node_relation = node_relation
    sm_model.entities = ["user_id"]
    sm_model.measures = ["amount"]
    sm_model.dimensions = ["created_at"]

    # Create a metric in the semantic model
    sm_metric = MagicMock(spec=Metric)
    sm_metric.name = "semantic_test_metric"
    sm_metric.description = "Semantic test metric description"
    sm_metric.type = "SUM"
    sm_metric.type_params = MagicMock()
    sm_metric.type_params.metrics = []
    sm_model.metrics = [sm_metric]

    semantic_manifest.semantic_models = [sm_model]
    semantic_manifest.get_metrics.return_value = [sm_metric]

    # Attach to context
    context.manifest = manifest
    context.semantic_manifest = semantic_manifest
    context.adapter_type = "postgres"
    context.credentials = {"host": "localhost", "database": "test_db"}

    return context


def test_lineage_mapper_includes_metrics_and_semantic_models(mock_context):
    """Test that the lineage mapper includes metrics and semantic models."""
    # Create generator and mapper
    generator = create_generator(mock_context.adapter_type, mock_context.credentials)
    mapper = DbtLineageMapper(mock_context, generator)

    # Map entities
    result = mapper.map()

    # We expect 4 entities: 1 model, 1 manifest metric, 1 semantic model, and 1 semantic metric
    assert len(result.items) == 4

    # Check that we have the right types of entities
    entity_types = {entity.name: entity.type for entity in result.items}
    assert entity_types.get("test_model") in [DataEntityType.TABLE, DataEntityType.VIEW]
    assert entity_types.get("test_metric") == DataEntityType.METRIC
    assert entity_types.get("test_semantic_model") == DataEntityType.ENTITY
    assert entity_types.get("semantic_test_metric") == DataEntityType.METRIC

    # Check the relationships
    for entity in result.items:
        if entity.name == "test_metric":
            # Metric should have the model as input
            assert len(entity.data_transformer.inputs) == 1

        if entity.name == "semantic_test_metric":
            # Semantic metric should have the semantic model as input
            assert len(entity.data_transformer.inputs) == 1
