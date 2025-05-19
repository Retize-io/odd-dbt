class Credentials:
    def __init__(self, **config) -> None:
        # Safely remove password if it exists
        if "password" in config:
            del config["password"]
        self._config: dict[str, str] = config

    def __getitem__(self, item):
        # Return None for missing keys instead of raising KeyError
        return self._config.get(item)

    def get(self, key, default=None):
        # Add a get method similar to dict.get()
        return self._config.get(key, default)
