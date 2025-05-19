from dbt.contracts.graph.nodes import (
    ColumnInfo,
    ModelNode,
    TestNode,
)
from dbt.contracts.graph.nodes import (
    Metric as MetricNode,
)
from dbt.contracts.graph.nodes import (
    SemanticModel as SemanticModelNode,
)
from odd_models import MetadataExtension

from odd_dbt.domain.semantic_manifest import Metric, SemanticModel


def get_metadata(test_node: TestNode) -> MetadataExtension:
    metadata = {
        "name": test_node.name,
        "alias": test_node.alias,
        "build_path": test_node.build_path,
        "compiled": test_node.compiled,
        "compiled_code": test_node.compiled_code,
        "compiled_path": test_node.compiled_path,
        "created_at": test_node.created_at,
        "database": test_node.database,
        "deferred": test_node.deferred if hasattr(test_node, "deferred") else False,
        "description": test_node.description,
        "extra_ctes_injected": test_node.extra_ctes_injected,
        "fqn": ", ".join(test_node.fqn),
        "language": test_node.language,
        "original_file_path": test_node.original_file_path,
        "package_name": test_node.package_name,
        "path": test_node.path,
    }

    schema_url = "https://raw.githubusercontent.com/opendatadiscovery/opendatadiscovery-specification/main/specification/extensions/dbt.json#/definitions/DataQualityTestRun"
    return MetadataExtension(schema_url=schema_url, metadata=metadata)


def get_model_metadata(model_node: ModelNode) -> list[MetadataExtension]:
    # We need to convert the model_node to a simpler dictionary
    # MetadataExtension expects simple types, not complex objects
    metadata = {
        "name": model_node.name,
        "description": model_node.description,
        "original_file_path": model_node.original_file_path,
        "package_name": model_node.package_name,
        "schema": model_node.schema,
        "database": model_node.database,
        "materialized": model_node.config.materialized
        if hasattr(model_node.config, "materialized")
        else None,
    }
    schema_url = "https://raw.githubusercontent.com/opendatadiscovery/opendatadiscovery-specification/main/specification/extensions/dbt.json#/definitions/DataTransformer"
    return [MetadataExtension(schema_url=schema_url, metadata=metadata)]


def get_column_metadata(column_info: ColumnInfo) -> MetadataExtension:
    # Create a simple dict with only primitive types
    metadata = {
        "name": column_info.name,
        "description": column_info.description or "",
        "data_type": column_info.data_type or "",
    }

    # Since ColumnInfo doesn't have a 'type' attribute (confirmed from components.py),
    # we'll use data_type as the type
    metadata["type"] = column_info.data_type or ""

    schema_url = "https://raw.githubusercontent.com/opendatadiscovery/opendatadiscovery-specification/main/specification/extensions/dbt.json#/definitions/DataSetField"
    return MetadataExtension(schema_url=schema_url, metadata=metadata)


def get_metric_metadata(metric_node: MetricNode) -> MetadataExtension:
    """Create metadata extension for a dbt metric from manifest.json"""
    # Create a simple dict with only primitive types
    metadata = {
        "name": metric_node.name,
        "description": metric_node.description,
        "package_name": metric_node.package_name
        if hasattr(metric_node, "package_name")
        else "",
        "path": metric_node.path if hasattr(metric_node, "path") else "",
        "unique_id": metric_node.unique_id if hasattr(metric_node, "unique_id") else "",
        "type": metric_node.type if hasattr(metric_node, "type") else "",
    }
    schema_url = "https://raw.githubusercontent.com/opendatadiscovery/opendatadiscovery-specification/main/specification/extensions/dbt.json#/definitions/Metric"
    return MetadataExtension(schema_url=schema_url, metadata=metadata)


def get_semantic_model_metadata(
    semantic_model_node: SemanticModelNode,
) -> MetadataExtension:
    """Create metadata extension for a dbt semantic model from manifest.json"""
    # Create a simple dict with only primitive types
    metadata = {
        "name": semantic_model_node.name,
        "description": semantic_model_node.description
        if hasattr(semantic_model_node, "description")
        else "",
        "package_name": semantic_model_node.package_name
        if hasattr(semantic_model_node, "package_name")
        else "",
        "path": semantic_model_node.path
        if hasattr(semantic_model_node, "path")
        else "",
        "unique_id": semantic_model_node.unique_id
        if hasattr(semantic_model_node, "unique_id")
        else "",
    }
    schema_url = "https://raw.githubusercontent.com/opendatadiscovery/opendatadiscovery-specification/main/specification/extensions/dbt.json#/definitions/SemanticModel"
    return MetadataExtension(schema_url=schema_url, metadata=metadata)


def get_semantic_manifest_model_metadata(
    semantic_model: SemanticModel,
) -> MetadataExtension:
    """Create metadata extension for a semantic model from semantic_manifest.json"""
    metadata = {
        "name": semantic_model.name,
        "description": semantic_model.description,
        "node_relation": {
            "alias": semantic_model.node_relation.alias,
            "schema_name": semantic_model.node_relation.schema_name,
            "database": semantic_model.node_relation.database,
            "relation_name": semantic_model.node_relation.relation_name,
        },
        "entities": semantic_model.entities,
        "measures": semantic_model.measures,
        "dimensions": semantic_model.dimensions,
        "metrics_count": len(semantic_model.metrics),
        "saved_queries_count": len(semantic_model.saved_queries),
    }

    schema_url = "https://raw.githubusercontent.com/opendatadiscovery/opendatadiscovery-specification/main/specification/extensions/dbt.json#/definitions/SemanticModel"
    return MetadataExtension(schema_url=schema_url, metadata=metadata)


def get_semantic_metric_metadata(metric: Metric) -> MetadataExtension:
    """Create metadata extension for a metric from semantic_manifest.json"""
    metadata = {
        "name": metric.name,
        "description": metric.description,
        "type": metric.data_type,
        "type_params": {
            "measure": metric.type_params.measure,
            "numerator": metric.type_params.numerator,
            "denominator": metric.type_params.denominator,
            "expr": metric.type_params.expr,
            "window": metric.type_params.window,
            "grain_to_date": metric.type_params.grain_to_date,
            "metrics_count": len(metric.type_params.metrics),
            "input_measures_count": len(metric.type_params.input_measures),
        },
        "filter": metric.filter,
    }

    if metric.metadata:
        metadata["custom_metadata"] = metric.metadata

    schema_url = "https://raw.githubusercontent.com/opendatadiscovery/opendatadiscovery-specification/main/specification/extensions/dbt.json#/definitions/Metric"
    return MetadataExtension(schema_url=schema_url, metadata=metadata)
