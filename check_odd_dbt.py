import json
import os
import sys
from pathlib import Path
from typing import Optional

from odd_dbt.domain.context import DbtContext
from odd_dbt.libs import dbt, odd
from odd_dbt.logger import logger
from odd_dbt.mapper.lineage import DbtLineageMapper
from odd_dbt.mapper.test_results import DbtTestMapper
from odd_dbt.service.dbt import CliArgs
import logging


def check_directory_structure(project_dir: Path) -> None:
    """Validate the basic directory structure of a dbt project."""
    logger.info(f"Checking dbt project structure in {project_dir}...")

    # Essential dbt project files/folders
    essential_items = [
        "dbt_project.yml",
        "models",
        "target/manifest.json",
    ]

    missing_items = []
    for item in essential_items:
        if not (project_dir / item).exists():
            missing_items.append(item)

    if missing_items:
        logger.error(f"Missing essential dbt items: {', '.join(missing_items)}")
        sys.exit(1)

    logger.info("✓ Directory structure looks valid")


def load_dbt_context(project_dir: Path, profiles_dir: Path) -> DbtContext:
    """Load the dbt context and validate essential components."""
    logger.info(f"Loading dbt context from {project_dir}...")

    cli_args = CliArgs(
        project_dir=project_dir,
        profiles_dir=profiles_dir,
        profile=None,
        target=None,
        threads=1,
        vars={},
    )

    try:
        context = dbt.get_context(cli_args=cli_args)
        logger.info("✓ Successfully loaded dbt context")
        return context
    except Exception as e:
        logger.error(f"Failed to load dbt context: {e}")
        import traceback

        logger.error(traceback.format_exc())
        sys.exit(1)


def validate_run_results(context: DbtContext) -> bool:
    """Check if run results are available and valid."""
    if context.run_results is None:
        logger.warning("⚠ run_results.json is not available or couldn't be loaded")
        return False

    try:
        invocation_id = context.run_results.invocation_id
        results_count = len(context.results)
        logger.info(f"✓ Found run_results with invocation_id: {invocation_id}")
        logger.info(f"✓ Results count: {results_count}")
        return True
    except Exception as e:
        logger.error(f"❌ Error accessing run results: {e}")
        return False


def validate_manifest(context: DbtContext) -> bool:
    """Check if manifest is available and valid."""
    try:
        nodes_count = len(context.manifest.nodes)
        sources_count = len(context.manifest.sources)
        logger.info(
            f"✓ Found manifest with {nodes_count} nodes and {sources_count} sources"
        )
        return True
    except Exception as e:
        logger.error(f"❌ Error accessing manifest: {e}")
        return False


def check_adapter_support(context: DbtContext) -> None:
    """Check which adapters are supported."""
    try:
        adapter_type = context.adapter_type
        logger.info(f"✓ Current adapter type: {adapter_type}")

        # List all supported adapters
        from odd_dbt.mapper.generator import ODDRN_GENERATORS

        supported_adapters = list(ODDRN_GENERATORS.keys())
        logger.info(f"✓ Supported adapters: {', '.join(supported_adapters)}")
    except Exception as e:
        logger.error(f"❌ Error checking adapter support: {e}")


def map_and_print_entities(
    context: DbtContext, output_file: Optional[str] = None
) -> None:
    """Map all entities and optionally save to file."""
    generator = odd.create_dbt_generator(host="localhost")

    # Initialize entities containers
    lineage_entities = None
    test_entities = None

    # Map lineage
    try:
        logger.info("Mapping lineage entities...")
        lineage_entities = DbtLineageMapper(context=context, generator=generator).map()
        logger.info(
            f"✓ Successfully mapped {len(lineage_entities.items)} lineage entities"
        )

        # Print a sample of lineage entities for review
        if lineage_entities.items:
            logger.info("Sample lineage entity:")
            logger.info(f"  - Type: {lineage_entities.items[0].type}")
            logger.info(f"  - ODDRN: {lineage_entities.items[0].oddrn}")
            logger.info(f"  - Name: {lineage_entities.items[0].name}")
    except Exception as e:
        logger.error(f"❌ Lineage mapping failed: {e}")

    # Map test results if available
    if context.results:
        try:
            logger.info("Mapping test result entities...")
            test_entities = DbtTestMapper(context=context, generator=generator).map()
            logger.info(
                f"✓ Successfully mapped {len(test_entities.items)} test result entities"
            )

            # Print a sample of test entities for review
            if test_entities.items and len(test_entities.items) > 1:
                logger.info("Sample test entities:")
                # Job entity
                job = test_entities.items[0]
                logger.info(f"  - Job Type: {job.type}")
                logger.info(f"  - Job ODDRN: {job.oddrn}")
                logger.info(f"  - Job Name: {job.name}")
                # Run entity
                run = test_entities.items[1]
                logger.info(f"  - Run Type: {run.type}")
                logger.info(f"  - Run Status: {run.data_quality_test_run.status}")

            # Save complete output if requested
            if output_file:
                with open(output_file, "w") as f:
                    combined_entities = {
                        "data_source_oddrn": generator.get_data_source_oddrn()
                    }
                    # Add lineage items if available
                    if lineage_entities and hasattr(lineage_entities, "items"):
                        combined_entities["lineage_items"] = [
                            item.model_dump(exclude_none=True)
                            for item in lineage_entities.items
                        ]
                    else:
                        combined_entities["lineage_items"] = []
                    # Add test items
                    combined_entities["test_items"] = [
                        item.model_dump(exclude_none=True)
                        for item in test_entities.items
                    ]
                    json.dump(combined_entities, f, indent=2, default=str)
                logger.info(f"✓ Saved complete output to {output_file}")
        except Exception as e:
            logger.error(f"❌ Test results mapping failed: {e}")
    else:
        logger.warning("⚠ No test results available to map")


def main():
    project_dir = Path("./example")
    profiles_dir = Path(os.path.expanduser("~/.dbt"))
    output_file = "odd_dbt_output.json"

    # Step 1: Check directory structure
    check_directory_structure(project_dir)

    # Step 2: Load dbt context
    context = load_dbt_context(project_dir, profiles_dir)

    # Step 3: Validate components
    has_run_results = validate_run_results(context)  # noqa: F841
    has_manifest = validate_manifest(context)
    check_adapter_support(context)

    # Step 4: Map and print entities
    if has_manifest:  # We need at least the manifest
        map_and_print_entities(context, output_file)

    logger.info("Check completed successfully!")


if __name__ == "__main__":
    main()
