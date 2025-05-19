from oddrn_generator import generators as odd
from oddrn_generator.generators import Generator as OddGenerator

from odd_dbt.patches.path_models import BigQueryPathsModel


# Create a custom BigQuery generator that uses our enhanced path model
class PatchedBigQueryGenerator(OddGenerator):
    """
    Enhanced BigQuery generator that uses our custom BigQueryPathsModel.
    This provides proper support for views and other BigQuery constructs.
    """

    source = "bigquery"
    paths_model = BigQueryPathsModel
    server_model = odd.GCPCloudModel
