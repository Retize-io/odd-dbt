#!/usr/bin/env python3
import os
import sys
from pathlib import Path

from odd_dbt.libs import dbt, odd
from odd_dbt.logger import logger
from odd_dbt.mapper.lineage import DbtLineageMapper
from odd_dbt.mapper.test_results import DbtTestMapper
from odd_dbt.service.dbt import CliArgs


def main():
    project_dir = Path("./example")
    profiles_dir = Path(os.path.expanduser("~/.dbt"))

    logger.info(
        f"Checking run_results.json in {project_dir / 'target' / 'run_results.json'}"
    )
    if not (project_dir / "target" / "run_results.json").exists():
        logger.error("run_results.json file not found!")
        sys.exit(1)

    logger.info("File exists, loading context...")

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
        logger.info("Successfully loaded context")

        if context.run_results is None:
            logger.error("context.run_results is None!")
            sys.exit(1)

        logger.info(
            f"Loaded run_results with invocation_id: {context.run_results.invocation_id}"
        )
        logger.info(f"Results count: {len(context.results)}")

        # Create generator for testing
        generator = odd.create_dbt_generator(host="localhost")

        # Test lineage mapping
        try:
            logger.info("Testing lineage mapping...")
            lineage_entities = DbtLineageMapper(
                context=context, generator=generator
            ).map()
            logger.info(
                f"Successfully mapped {len(lineage_entities.items)} lineage entities"
            )
        except Exception as e:
            logger.error(f"Lineage mapping failed: {e}")

        # Test test results mapping
        if context.results:
            try:
                logger.info("Testing test results mapping...")
                test_entities = DbtTestMapper(
                    context=context, generator=generator
                ).map()
                logger.info(
                    f"Successfully mapped {len(test_entities.items)} test entities"
                )
            except Exception as e:
                logger.error(f"Test results mapping failed: {e}")
    except Exception as e:
        logger.error(f"Error getting context: {e}")
        import traceback

        logger.error(traceback.format_exc())
        sys.exit(1)

    logger.info("Script completed successfully")


if __name__ == "__main__":
    main()
