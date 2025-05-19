import os
import sys
from pathlib import Path

# Import our custom BigQuery generator extension
from dotenv import load_dotenv
from odd_dbt import config
from odd_dbt.domain.cli_args import CliArgs
from odd_dbt.libs.dbt import get_context
from odd_dbt.libs.odd import DbtGeneratorWrapper
from odd_dbt.logger import logger
from odd_dbt.mapper.generator import create_generator
from odd_dbt.mapper.lineage import DbtLineageMapper
from odd_dbt.mapper.test_results import DbtTestMapper
from odd_dbt.service.odd import ingest_entities


def main():
    # Load environment variables from .env file
    load_dotenv()

    # Get environment variables
    odd_platform_host = os.getenv("ODD_PLATFORM_HOST")
    odd_platform_token = os.getenv("ODD_PLATFORM_TOKEN")
    gcp_project_id = os.getenv("GCP_PROJECT_ID", "your-gcp-project-id")
    dbt_data_source_oddrn = os.getenv("DBT_DATA_SOURCE_ODDRN")

    if not odd_platform_host or not odd_platform_token:
        logger.error(
            "Missing required environment variables. Please check your .env file."
        )
        logger.error("Required variables: ODD_PLATFORM_HOST, ODD_PLATFORM_TOKEN")
        sys.exit(1)

    # Set your dbt project configuration
    # Path to your dbt project (you can specify the full path to your actual project)
    project_dir = Path(os.getenv("DBT_PROJECT_DIR", "./example"))
    profiles_dir = Path(
        os.getenv("DBT_PROFILES_DIR", os.path.expanduser("~/.dbt"))
    )  # Update if your profiles are elsewhere
    profile = None  # Specify your profile name or None to use the default
    target = None  # Specify your target name or None to use the default

    # Create ODD client
    client = config.create_odd_client(host=odd_platform_host, token=odd_platform_token)

    # Create a BigQuery-specific generator
    logger.info(f"Creating BigQuery generator with project ID: {gcp_project_id}")
    bigquery_generator = create_generator("bigquery", {"project": gcp_project_id})
    generator = DbtGeneratorWrapper(bigquery_generator)

    # Get the data source ODDRN from the generator
    generated_oddrn = bigquery_generator.get_data_source_oddrn()

    # If we have a saved ODDRN but it doesn't match our current generator's ODDRN,
    # log a warning as this might cause issues
    if dbt_data_source_oddrn and dbt_data_source_oddrn != generated_oddrn:
        logger.warning(
            f"Saved ODDRN {dbt_data_source_oddrn} doesn't match generated ODDRN {generated_oddrn}"
        )
        logger.warning("Using the generated ODDRN to ensure consistency")

    # Always use the freshly generated ODDRN
    dbt_data_source_oddrn = generated_oddrn

    # Create data source if needed
    try:
        data_source_name = "Retize DBT BigQuery Project"  # Descriptive name for ODD UI
        logger.info(f"Creating/updating data source with name: {data_source_name}")
        logger.info(f"Using ODDRN: {dbt_data_source_oddrn}")

        client.create_data_source(
            data_source_name=data_source_name,
            data_source_oddrn=dbt_data_source_oddrn,
        )
        logger.info(f"Data source ready with ODDRN: {dbt_data_source_oddrn}")
        logger.info(
            "Add this to your .env file as DBT_DATA_SOURCE_ODDRN for future use"
        )
    except Exception as e:
        logger.error(f"Failed to create/update data source: {e}")
        sys.exit(1)

    # Create dbt context
    logger.info(f"Loading dbt context from {project_dir}")
    cli_args = CliArgs(
        project_dir=project_dir,
        profiles_dir=profiles_dir,
        profile=profile,
        target=target,
        threads=1,
        vars={},
    )

    try:
        context = get_context(cli_args=cli_args)
        logger.info("Successfully loaded dbt context")
    except Exception as e:
        logger.error(f"Failed to load dbt context: {e}")
        sys.exit(1)

    # We're using the dbt_generator we created earlier - don't recreate it from the ODDRN

    # Process and ingest lineage data
    try:
        logger.info("Mapping lineage data...")
        lineage_entities = DbtLineageMapper(context=context, generator=generator).map()
        logger.info(f"Found {len(lineage_entities.items or [])} lineage entities")

        logger.info("Ingesting lineage data to ODD platform...")
        ingest_entities(lineage_entities, client)
        logger.success("Successfully ingested lineage data")
    except Exception as e:
        logger.error(f"Error processing lineage data: {e}")
        import traceback

        logger.debug(traceback.format_exc())

    # Process and ingest test results if available
    if context.run_results:
        try:
            logger.info("Mapping test results...")
            test_entities = DbtTestMapper(context=context, generator=generator).map()
            logger.info(f"Found {len(test_entities.items or [])} test entities")

            logger.info("Ingesting test results to ODD platform...")
            ingest_entities(test_entities, client)
            logger.success("Successfully ingested test results")
        except Exception as e:
            logger.error(f"Error processing test results: {e}")
            import traceback

            logger.debug(traceback.format_exc())
    else:
        logger.warning(
            "No test results found. Run 'dbt test' to generate test results."
        )

    logger.info("Data upload completed!")


if __name__ == "__main__":
    main()
