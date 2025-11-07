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

# Plugins are auto-discovered by ha_enviro_plus.display_plugins
# Do NOT import plugins here directly - it causes circular import issues
# The display_plugins module will import plugins after register_plugin is defined
