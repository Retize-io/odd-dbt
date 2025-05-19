from typing import Optional

from oddrn_generator.path_models import BasePathsModel, DependenciesMap
from pydantic import Field


# Extended path model for BigQuery that adds support for views
class BigQueryPathsModel(BasePathsModel):
    """
    Enhanced BigQuery path model that adds support for views and other BigQuery constructs.
    This extends the standard BigQueryStoragePathsModel to include paths necessary for DBT integration.
    """

    datasets: Optional[str] = None
    tables: Optional[str] = None
    views: Optional[str] = None
    routines: Optional[str] = None  # For stored procedures, UDFs
    tables_columns: Optional[str] = Field(None, alias="columns")
    views_columns: Optional[str] = Field(None, alias="columns")
    # Add dbt-specific paths
    metrics: Optional[str] = None  # For dbt metrics
    semantic_models: Optional[str] = None  # For dbt semantic models
    seeds: Optional[str] = None  # For dbt seed files

    @classmethod
    def _dependencies_map_factory(cls):
        return {
            "datasets": ("datasets",),
            "tables": ("datasets", "tables"),
            "views": ("datasets", "views"),
            "routines": ("datasets", "routines"),
            "tables_columns": ("datasets", "tables", "tables_columns"),
            "views_columns": ("datasets", "views", "views_columns"),
            # Dependencies for dbt-specific paths
            "metrics": ("metrics",),  # Metrics are top-level resources
            "semantic_models": (
                "semantic_models",
            ),  # Semantic models are top-level resources
            "seeds": ("datasets", "seeds"),  # Seeds belong in datasets
        }

    dependencies_map: DependenciesMap = Field(
        default_factory=lambda: BigQueryPathsModel._dependencies_map_factory()
    )


# PostgreSQL path model for test paths
class PostgresqlPathsModel(BasePathsModel):
    """
    PostgreSQL path model that adds support for tests and other PostgreSQL constructs.
    This model defines the paths used by the oddrn-generator for PostgreSQL databases.
    """

    schemas: Optional[str] = None
    tables: Optional[str] = None
    views: Optional[str] = None
    routines: Optional[str] = None  # For stored procedures, UDFs
    columns: Optional[str] = None
    tests: Optional[str] = None  # Support for dbt test paths

    @classmethod
    def _dependencies_map_factory(cls):
        return {
            "schemas": ("schemas",),
            "tables": ("schemas", "tables"),
            "views": ("schemas", "views"),
            "routines": ("schemas", "routines"),
            "columns": ("schemas", "tables", "columns"),
            "tests": ("schemas", "tests"),  # Add test path mappings
        }

    dependencies_map: DependenciesMap = Field(
        default_factory=lambda: PostgresqlPathsModel._dependencies_map_factory()
    )
