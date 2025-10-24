# Contributing to ha-enviro-plus

Thank you for your interest in contributing to ha-enviro-plus! This document provides guidelines and information for contributors.

## Development Environment Setup

### Prerequisites

- Python 3.9 or higher
- Git
- Raspberry Pi with Enviro+ (optional, for hardware testing)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/JeffLuckett/ha-enviro-plus.git
   cd ha-enviro-plus
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install in development mode**
   ```bash
   pip install -e .
   ```

4. **Install development dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

## Running Tests

### Test Structure

- `tests/unit/` - Unit tests with mocked hardware
- `tests/integration/` - Integration tests with mock MQTT broker
- `tests/hardware/` - Hardware tests requiring real Enviro+ sensors

### Running Tests

```bash
# Run all tests (excluding hardware)
pytest tests/ -m "not hardware"

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run hardware tests (requires Enviro+ hardware)
pytest tests/hardware/

# Run with coverage
pytest tests/ --cov=ha_enviro_plus --cov-report=html

# Run specific test file
pytest tests/unit/test_sensors.py

# Run specific test
pytest tests/unit/test_sensors.py::TestEnviroPlusSensorsInit::test_init_default_values
```

### Test Coverage

The project aims for >=75% test coverage with all critical paths and edge cases covered. Coverage reports are generated in HTML format in the `htmlcov/` directory.

## Code Quality

### Linting and Formatting

```bash
# Check code formatting
black --check ha_enviro_plus tests

# Format code
black ha_enviro_plus tests

# Lint code
flake8 ha_enviro_plus tests

# Type checking
mypy ha_enviro_plus --ignore-missing-imports
```

### Pre-commit Hooks

Consider setting up pre-commit hooks to automatically run linting and formatting:

```bash
pip install pre-commit
pre-commit install
```

## Writing Tests

### Test Writing Guidelines

1. **Test Structure**: Follow the existing test structure with descriptive class and method names
2. **Fixtures**: Use shared fixtures from `tests/conftest.py` for common mocks
3. **Coverage**: Aim for comprehensive coverage of all public methods and edge cases
4. **Hardware Tests**: Mark hardware tests with `@pytest.mark.hardware` and `@pytest.mark.skipif`

### Example Test Structure

```python
class TestNewFeature:
    """Test new feature functionality."""

    def test_basic_functionality(self, mock_fixture):
        """Test basic functionality."""
        # Arrange
        obj = NewFeature()

        # Act
        result = obj.method()

        # Assert
        assert result == expected_value

    @pytest.mark.parametrize("input,expected", [
        (1, 2),
        (2, 4),
        (3, 6),
    ])
    def test_with_parameters(self, input, expected):
        """Test with multiple parameters."""
        assert input * 2 == expected
```

### Hardware Testing

Hardware tests are marked with `@pytest.mark.hardware` and will be skipped if hardware is not available:

```python
@pytest.mark.hardware
@pytest.mark.skipif(not hardware_available(), reason="Hardware not detected")
def test_real_sensor():
    """Test with real hardware."""
    sensors = EnviroPlusSensors()
    assert sensors.temp() > 0
```

## Pull Request Process

### Before Submitting

1. **Run Tests**: Ensure all tests pass
   ```bash
   pytest tests/ -m "not hardware"
   ```

2. **Check Code Quality**: Run linting and formatting
   ```bash
   black --check ha_enviro_plus tests
   flake8 ha_enviro_plus tests
   mypy ha_enviro_plus --ignore-missing-imports
   ```

3. **Update Tests**: Add tests for new functionality
4. **Update Documentation**: Update README.md if needed

### Pull Request Requirements

- [ ] All tests pass
- [ ] Code coverage is maintained (>=75% with critical paths covered)
- [ ] Code follows project style guidelines
- [ ] New functionality includes tests
- [ ] Documentation is updated if needed
- [ ] Commit messages are descriptive

### Commit Message Format

Use descriptive commit messages:

```
Add temperature compensation feature

- Implement CPU temperature compensation algorithm
- Add configurable compensation factor
- Include comprehensive tests
- Update documentation
```

## Project Structure

```
ha_enviro_plus/          # Main package
├── __init__.py         # Package initialization
├── sensors.py          # Sensor management
└── agent.py            # MQTT agent

tests/                  # Test suite
├── conftest.py         # Shared fixtures
├── unit/               # Unit tests
├── integration/        # Integration tests
└── hardware/           # Hardware tests

scripts/                # Installation scripts
├── install.sh
├── uninstall.sh
└── update-version.sh   # Version management script

.github/workflows/      # CI/CD
└── test.yml
```

## Development Guidelines

### Code Style

- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Write descriptive docstrings
- Use meaningful variable and function names

### Version Management

The project uses a single source of truth for versioning in `ha_enviro_plus/__init__.py`. To update the version across all files:

```bash
# Update version to 0.2.0 (manual process)
./scripts/update-version.sh 0.2.0

# Review changes
git diff

# Commit and tag
git commit -m "Bump version to 0.2.0"
git tag v0.2.0
git push && git push --tags
```

**Or use the automated release process:**

```bash
# Update version and create GitHub release automatically
./scripts/update-version.sh 0.2.0 --release
```

The version update script automatically updates:
- `ha_enviro_plus/__init__.py` (source of truth)
- `ha_enviro_plus/agent.py` (MQTT device info)
- `README.md` version section
- `scripts/install.sh` fallback version

### GitHub Releases

The project uses GitHub Releases for distribution. When you create a version tag (e.g., `v0.2.0`), GitHub Actions automatically:

1. **Runs all tests** to ensure quality
2. **Builds the package** (wheel and source distribution)
3. **Generates changelog** from conventional commits
4. **Creates release** with:
   - Release notes from changelog
   - Installation instructions
   - Download links for source code
   - Built package artifacts

**Release Process:**
```bash
# Option 1: Automated (recommended)
./scripts/update-version.sh 0.2.0 --release

# Option 2: Manual
./scripts/update-version.sh 0.2.0
git commit -m "Bump version to 0.2.0"
git tag v0.2.0
git push && git push --tags
```

**Release URLs:**
- Releases: https://github.com/JeffLuckett/ha-enviro-plus/releases
- Latest: https://github.com/JeffLuckett/ha-enviro-plus/releases/latest

### Documentation

- Update docstrings for new functions/classes
- Update README.md for new features
- Include examples in docstrings

## Hardware Testing

If you have Enviro+ hardware available:

1. **Connect Hardware**: Ensure Enviro+ is properly connected
2. **Run Hardware Tests**: `pytest tests/hardware/`
3. **Verify Readings**: Check that sensor readings are reasonable

Hardware tests will be skipped automatically if hardware is not detected.

## Getting Help

- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Discussions**: Use GitHub Discussions for questions and general discussion
- **Documentation**: Check README.md and code comments

## License

By contributing to ha-enviro-plus, you agree that your contributions will be licensed under the MIT License.
