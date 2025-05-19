from odd_models import DataEntity

from odd_dbt.mapper.generator import create_generator


# Create a wrapper class that adapts our implementation to work with oddrn_generator.DbtGenerator
class DbtGeneratorWrapper:
    def __init__(self, inner_generator):
        self.inner_generator = inner_generator

    def __getattr__(self, name):
        return getattr(self.inner_generator, name)

    def get_data_source_oddrn(self) -> str:
        return self.inner_generator.get_data_source_oddrn()

    def get_oddrn_by_path(self, *args, **kwargs) -> str:
        return self.inner_generator.get_oddrn_by_path(*args, **kwargs)

    def set_oddrn_paths(self, **kwargs) -> None:
        # This method is expected by test_results.py
        # But our generators implement it differently or not at all
        # We'll adapt it to the expected interface here
        if hasattr(self.inner_generator, "set_oddrn_paths"):
            self.inner_generator.set_oddrn_paths(**kwargs)
        # Otherwise, store the paths for later use
        else:
            if not hasattr(self, "_paths"):
                self._paths = {}
            self._paths.update(kwargs)

    def get_oddrn_for(self, node) -> str:
        return self.inner_generator.get_oddrn_for(node)


def create_dbt_generator_from_oddrn(oddrn: str) -> DbtGeneratorWrapper:
    host = extract_host_from_oddrn(oddrn)
    # Use our custom generator implementation wrapped in the adapter
    inner_generator = create_generator("postgres", {"host": host})
    return DbtGeneratorWrapper(inner_generator)


def create_dbt_generator(host: str) -> DbtGeneratorWrapper:
    # Use our custom generator implementation wrapped in the adapter
    inner_generator = create_generator("postgres", {"host": host})
    return DbtGeneratorWrapper(inner_generator)


def extract_host_from_oddrn(oddrn: str) -> str:
    return oddrn.split("//dbt/host/")[-1]


def is_data_transformer(data_entity: DataEntity) -> bool:
    return data_entity.data_transformer is not None
