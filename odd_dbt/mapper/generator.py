import abc
from functools import singledispatchmethod
from typing import Any, Protocol, Type

from dbt.contracts.graph.nodes import (
    Metric as MetricNode,
)
from dbt.contracts.graph.nodes import ModelNode
from dbt.contracts.graph.nodes import (
    SemanticModel as SemanticModelNode,
)
from oddrn_generator import generators as odd

from odd_dbt.domain.credentials import Credentials
from odd_dbt.domain.semantic_manifest import Metric, SemanticModel
from odd_dbt.domain.source import Source
from odd_dbt.patches.generator import PatchedBigQueryGenerator


class Generator(Protocol):
    generator_cls: Type[odd.Generator]
    credentials: Credentials

    @singledispatchmethod
    def get_oddrn_for(self, node: Any) -> str: ...

    @get_oddrn_for.register
    def _(self, node: ModelNode) -> str:
        return self._get_oddrn_for_model(node)

    @get_oddrn_for.register
    def _(self, node: Source) -> str:
        return self._get_oddrn_for_source(node)

    @get_oddrn_for.register
    def _(self, node: MetricNode) -> str:
        return self._get_oddrn_for_metric(node)

    @get_oddrn_for.register
    def _(self, node: SemanticModelNode) -> str:
        return self._get_oddrn_for_semantic_model(node)

    @get_oddrn_for.register
    def _(self, node: Metric) -> str:
        return self._get_oddrn_for_semantic_metric(node)

    @get_oddrn_for.register
    def _(self, node: SemanticModel) -> str:
        return self._get_oddrn_for_semantic_manifest_model(node)

    @abc.abstractmethod
    def _get_oddrn_for_model(self, model: ModelNode) -> str: ...

    @abc.abstractmethod
    def _get_oddrn_for_source(self, source: Source) -> str: ...

    @abc.abstractmethod
    def _get_oddrn_for_metric(self, metric: MetricNode) -> str: ...

    @abc.abstractmethod
    def _get_oddrn_for_semantic_model(
        self, semantic_model: SemanticModelNode
    ) -> str: ...

    @abc.abstractmethod
    def _get_oddrn_for_semantic_metric(self, metric: Metric) -> str: ...

    @abc.abstractmethod
    def _get_oddrn_for_semantic_manifest_model(
        self, semantic_model: SemanticModel
    ) -> str: ...

    @abc.abstractmethod
    def get_data_source_oddrn(self) -> str: ...

    @abc.abstractmethod
    def get_oddrn_by_path(self, *args, **kwargs) -> str: ...

    @abc.abstractmethod
    def set_oddrn_paths(self, **kwargs) -> None: ...


class PostgresGenerator(Generator):
    generator_cls = odd.PostgresqlGenerator

    def __init__(self, credentials: Credentials) -> None:
        self.credentials = credentials
        self._paths = {}
        self._generator = None

    def _get_base_generator(self):
        # Get or create the base generator
        if self._generator is None:
            host = self.credentials.get("host", "localhost")
            database = self.credentials.get("database") or self.credentials.get(
                "dbname", "default"
            )
            self._generator = self.generator_cls(host_settings=host, databases=database)
        return self._generator

    def _get_oddrn_for_model(self, model: ModelNode) -> str:
        # Safely access credentials with get() to avoid KeyError
        generator = self._get_base_generator()
        path = "views" if model.config.materialized == "view" else "tables"
        generator.set_oddrn_paths(**{"schemas": model.schema})
        return generator.get_oddrn_by_path(path, model.name)

    def _get_oddrn_for_source(self, source: Source) -> str:
        # Safely access credentials with get() to avoid KeyError
        host = self.credentials.get("host", "localhost")
        database = source.database
        generator = self.generator_cls(host_settings=host, databases=database)
        generator.set_oddrn_paths(**{"schemas": source.schema, "tables": source.name})
        return generator.get_oddrn_by_path("tables")

    def _get_oddrn_for_metric(self, metric: MetricNode) -> str:
        # Create ODDRN for metrics from manifest
        host = self.credentials.get("host", "localhost")
        database = self.credentials.get("database") or self.credentials.get(
            "dbname", "default"
        )
        generator = self.generator_cls(host_settings=host, databases=database)

        # Using a custom path for metrics - they're not directly tables/views
        generator.set_oddrn_paths(**{"schemas": "dbt_metrics"})
        return generator.get_oddrn_by_path("metrics", metric.name)

    def _get_oddrn_for_semantic_model(self, semantic_model: SemanticModelNode) -> str:
        # Create ODDRN for semantic models from manifest
        host = self.credentials.get("host", "localhost")
        database = self.credentials.get("database") or self.credentials.get(
            "dbname", "default"
        )
        generator = self.generator_cls(host_settings=host, databases=database)

        # Using a custom path for semantic models
        generator.set_oddrn_paths(**{"schemas": "dbt_semantic_models"})
        return generator.get_oddrn_by_path("semantic_models", semantic_model.name)

    def _get_oddrn_for_semantic_metric(self, metric: Metric) -> str:
        # Create ODDRN for metrics from semantic manifest
        host = self.credentials.get("host", "localhost")
        database = self.credentials.get("database") or self.credentials.get(
            "dbname", "default"
        )
        generator = self.generator_cls(host_settings=host, databases=database)

        # Using a custom path for semantic metrics
        generator.set_oddrn_paths(**{"schemas": "dbt_semantic_metrics"})
        return generator.get_oddrn_by_path("metrics", metric.name)

    def _get_oddrn_for_semantic_manifest_model(
        self, semantic_model: SemanticModel
    ) -> str:
        # Create ODDRN for semantic models from semantic manifest
        host = self.credentials.get("host", "localhost")

        # Use the database from the node_relation if available
        database = (
            semantic_model.node_relation.database
            if semantic_model.node_relation.database
            else (
                self.credentials.get("database")
                or self.credentials.get("dbname", "default")
            )
        )

        generator = self.generator_cls(host_settings=host, databases=database)

        # Using schema from node_relation if available, otherwise use a default
        schema = (
            semantic_model.node_relation.schema_name
            if semantic_model.node_relation.schema_name
            else "dbt_semantic_models"
        )

        generator.set_oddrn_paths(**{"schemas": schema})
        return generator.get_oddrn_by_path("semantic_models", semantic_model.name)

    def get_data_source_oddrn(self) -> str:
        """Create ODDRN for the data source"""
        host = self.credentials.get("host", "localhost")
        database = self.credentials.get("database") or self.credentials.get(
            "dbname", "default"
        )
        generator = self.generator_cls(host_settings=host, databases=database)
        return generator.get_data_source_oddrn()

    def get_oddrn_by_path(self, *args, **kwargs) -> str:
        """Get ODDRN by path from underlying generator"""
        generator = self._get_base_generator()
        return generator.get_oddrn_by_path(*args, **kwargs)

    def set_oddrn_paths(self, **kwargs) -> None:
        """Set ODDRN paths for underlying generator"""
        self._paths.update(kwargs)
        generator = self._get_base_generator()
        generator.set_oddrn_paths(**kwargs)


class SnowflakeGenerator(Generator):
    generator_cls = odd.SnowflakeGenerator

    def __init__(self, credentials: Credentials) -> None:
        self.credentials = credentials

    def _get_oddrn_for_model(self, model: ModelNode) -> str:
        # Safely access credentials with get() to avoid KeyError
        account = self.credentials.get("account", "unknown")
        host = f"{account.upper()}.snowflakecomputing.com"
        database = self.credentials.get("database") or self.credentials.get(
            "dbname", "default"
        )
        database = database.upper()

        generator = self.generator_cls(host_settings=host, databases=database)

        name = model.name.upper()
        path = "views" if model.config.materialized == "view" else "tables"
        generator.set_oddrn_paths(**{"schemas": model.schema.upper()})
        return generator.get_oddrn_by_path(path, name)

    def _get_oddrn_for_source(self, source: Source) -> str:
        # Safely access credentials with get() to avoid KeyError
        account = self.credentials.get("account", "unknown")
        host = f"{account.upper()}.snowflakecomputing.com"
        database = source.database.upper()

        generator = self.generator_cls(host_settings=host, databases=database)

        generator.set_oddrn_paths(**{
            "schemas": source.schema.upper(),
            "tables": source.name.upper(),
        })
        return generator.get_oddrn_by_path("tables")

    def _get_oddrn_for_metric(self, metric: MetricNode) -> str:
        # Create ODDRN for metrics from manifest
        account = self.credentials.get("account", "unknown")
        host = f"{account.upper()}.snowflakecomputing.com"
        database = self.credentials.get("database") or self.credentials.get(
            "dbname", "default"
        )
        database = database.upper()

        generator = self.generator_cls(host_settings=host, databases=database)

        # Using a custom path for metrics in Snowflake
        generator.set_oddrn_paths(**{"schemas": "DBT_METRICS"})
        return generator.get_oddrn_by_path("metrics", metric.name.upper())

    def _get_oddrn_for_semantic_model(self, semantic_model: SemanticModelNode) -> str:
        # Create ODDRN for semantic models from manifest
        account = self.credentials.get("account", "unknown")
        host = f"{account.upper()}.snowflakecomputing.com"
        database = self.credentials.get("database") or self.credentials.get(
            "dbname", "default"
        )
        database = database.upper()

        generator = self.generator_cls(host_settings=host, databases=database)

        # Using a custom path for semantic models in Snowflake
        generator.set_oddrn_paths(**{"schemas": "DBT_SEMANTIC_MODELS"})
        return generator.get_oddrn_by_path(
            "semantic_models", semantic_model.name.upper()
        )

    def _get_oddrn_for_semantic_metric(self, metric: Metric) -> str:
        # Create ODDRN for metrics from semantic manifest
        account = self.credentials.get("account", "unknown")
        host = f"{account.upper()}.snowflakecomputing.com"
        database = self.credentials.get("database") or self.credentials.get(
            "dbname", "default"
        )
        database = database.upper()

        generator = self.generator_cls(host_settings=host, databases=database)

        # Using a custom path for semantic metrics in Snowflake
        generator.set_oddrn_paths(**{"schemas": "DBT_SEMANTIC_METRICS"})
        return generator.get_oddrn_by_path("metrics", metric.name.upper())

    def _get_oddrn_for_semantic_manifest_model(
        self, semantic_model: SemanticModel
    ) -> str:
        # Create ODDRN for semantic models from semantic manifest
        account = self.credentials.get("account", "unknown")
        host = f"{account.upper()}.snowflakecomputing.com"

        # Use the database from the node_relation if available
        database = (
            semantic_model.node_relation.database.upper()
            if semantic_model.node_relation.database
            else (
                self.credentials.get("database")
                or self.credentials.get("dbname", "default")
            ).upper()
        )

        generator = self.generator_cls(host_settings=host, databases=database)

        # Using schema from node_relation if available, otherwise use a default
        schema = (
            semantic_model.node_relation.schema_name.upper()
            if semantic_model.node_relation.schema_name
            else "DBT_SEMANTIC_MODELS"
        )

        generator.set_oddrn_paths(**{"schemas": schema})
        return generator.get_oddrn_by_path(
            "semantic_models", semantic_model.name.upper()
        )

    def get_data_source_oddrn(self) -> str:
        """Create ODDRN for the data source"""
        account = self.credentials.get("account", "unknown")
        host = f"{account.upper()}.snowflakecomputing.com"
        database = self.credentials.get("database") or self.credentials.get(
            "dbname", "default"
        )
        database = database.upper()

        generator = self.generator_cls(host_settings=host, databases=database)
        return generator.get_data_source_oddrn()

    def get_oddrn_by_path(self, *args, **kwargs) -> str:
        # Delegate to the underlying generator class
        generator = self.generator_cls(
            host_settings=self.credentials.get("host", "localhost"),
            databases=self.credentials.get("database")
            or self.credentials.get("dbname", "default"),
        )
        return generator.get_oddrn_by_path(*args, **kwargs)

    def set_oddrn_paths(self, **kwargs) -> None:
        # Delegate to the underlying generator class
        generator = self.generator_cls(
            host_settings=self.credentials.get("host", "localhost"),
            databases=self.credentials.get("database")
            or self.credentials.get("dbname", "default"),
        )
        return generator.set_oddrn_paths(**kwargs)


# Import our enhanced BigQuery generator from patches


class BigQueryGenerator(Generator):
    """
    Enhanced BigQuery generator for DBT that properly handles all BigQuery object types.
    """

    generator_cls = PatchedBigQueryGenerator

    def __init__(self, credentials: Credentials) -> None:
        self.credentials = credentials

    def _get_oddrn_for_model(self, model: ModelNode) -> str:
        project_id = self.credentials["project"]
        dataset = model.schema
        name = model.name
        generator = self.generator_cls(
            google_cloud_settings={"project": project_id}, datasets=dataset
        )
        return generator.get_oddrn_by_path("tables", name)

    def _get_oddrn_for_source(self, source: Source) -> str:
        project_id = source.database
        dataset = source.schema
        generator = self.generator_cls(
            google_cloud_settings={"project": project_id}, datasets=dataset
        )

        generator.set_oddrn_paths(**{"tables": source.name})
        return generator.get_oddrn_by_path("tables")

    def _get_oddrn_for_metric(self, metric: MetricNode) -> str:
        project_id = self.credentials["project"]
        dataset = "dbt_metrics"  # Using a fixed dataset for metrics
        generator = self.generator_cls(
            google_cloud_settings={"project": project_id}, datasets=dataset
        )
        return generator.get_oddrn_by_path("metrics", metric.name)

    def _get_oddrn_for_semantic_model(self, semantic_model: SemanticModelNode) -> str:
        project_id = self.credentials["project"]
        dataset = "dbt_semantic_models"  # Using a fixed dataset for semantic models
        generator = self.generator_cls(
            google_cloud_settings={"project": project_id}, datasets=dataset
        )
        return generator.get_oddrn_by_path("semantic_models", semantic_model.name)

    def _get_oddrn_for_semantic_metric(self, metric: Metric) -> str:
        project_id = self.credentials["project"]
        dataset = "dbt_semantic_metrics"  # Using a fixed dataset for semantic metrics
        generator = self.generator_cls(
            google_cloud_settings={"project": project_id}, datasets=dataset
        )
        return generator.get_oddrn_by_path("metrics", metric.name)

    def _get_oddrn_for_semantic_manifest_model(
        self, semantic_model: SemanticModel
    ) -> str:
        # Use the database from the node_relation if available
        project_id = (
            semantic_model.node_relation.database
            if semantic_model.node_relation.database
            else self.credentials["project"]
        )

        # Using schema from node_relation if available
        dataset = (
            semantic_model.node_relation.schema_name
            if semantic_model.node_relation.schema_name
            else "dbt_semantic_models"
        )

        generator = self.generator_cls(
            google_cloud_settings={"project": project_id}, datasets=dataset
        )
        return generator.get_oddrn_by_path("semantic_models", semantic_model.name)

    def get_data_source_oddrn(self) -> str:
        """Create ODDRN for the data source"""
        project_id = self.credentials["project"]
        generator = self.generator_cls(google_cloud_settings={"project": project_id})
        return generator.get_data_source_oddrn()

    def get_oddrn_by_path(self, *args, **kwargs) -> str:
        # Delegate to the underlying generator class
        generator = self.generator_cls(
            google_cloud_settings={"project": self.credentials["project"]}
        )
        return generator.get_oddrn_by_path(*args, **kwargs)

    def set_oddrn_paths(self, **kwargs) -> None:
        # Delegate to the underlying generator class
        generator = self.generator_cls(
            google_cloud_settings={"project": self.credentials["project"]}
        )
        return generator.set_oddrn_paths(**kwargs)


ODDRN_GENERATORS: dict[str, Type[Generator]] = {
    "postgres": PostgresGenerator,
    "snowflake": SnowflakeGenerator,
    "bigquery": BigQueryGenerator,
}


def create_generator(adapter_type: str, credentials: Credentials) -> Generator:
    """
    :param adapter_type: Dbt adapter type
    :param credentials: Credentials for adapter
    :return: GeneratorWrapper
    """
    try:
        generator = ODDRN_GENERATORS[adapter_type]
        return generator(credentials)
    except KeyError as e:
        raise KeyError(
            f"Unsupported adapter type {adapter_type}. Available: {ODDRN_GENERATORS.keys()}"
        ) from e
