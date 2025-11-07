"""
Display Plugins Package

This package contains display plugins for the ha-enviro-plus system.
Plugins in this directory will be automatically discovered and registered.

Plugins in this directory:
- sensor_display.py: Default sensor display plugin (always registered)

To create a new plugin:
1. Create a new Python file in this directory
2. Import DisplayPlugin and register_plugin from
   ha_enviro_plus.display_plugins
3. Create a class extending DisplayPlugin
4. Use the @register_plugin decorator
5. Implement required methods: name(), is_available(),
   render(), duration()

See README.md in this directory for detailed instructions
and examples.
"""

# Import default plugin to ensure it's registered
from . import sensor_display  # noqa: F401

# Import individual sensor display plugins
from . import temperature_display  # noqa: F401
from . import humidity_display  # noqa: F401
from . import pressure_display  # noqa: F401
from . import noise_display  # noqa: F401
from . import gas_display  # noqa: F401

# This __init__.py exists to make this a package for auto-discovery.
# User plugins should import from ha_enviro_plus.display_plugins
