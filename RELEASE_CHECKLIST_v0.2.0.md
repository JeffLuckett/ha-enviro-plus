# v0.2.0 Release Checklist

## Pre-Release Verification

### Feature Completion
- [x] Noise sensor with dB(A) readings implemented
- [x] Proximity sensor tap detection implemented
- [x] Individual sensor display screens created:
  - [x] Temperature display
  - [x] Humidity display
  - [x] Pressure display
  - [x] Noise display
  - [x] Gas display (all 3 categories)
- [x] Display auto-rotation working (via plugin cycle)
- [x] Tap navigation integrated (advances plugin cycle)
- [x] Units support (metric/imperial) for all displays

### Documentation
- [x] ROADMAP.md updated (PM sensors moved to v0.3.0)
- [x] CHANGELOG.md updated (removed unimplemented features from Unreleased)
- [x] CHANGELOG.md v0.2.0 section reflects actual implementation
- [ ] README.md updated with new features (if needed)
- [ ] All documentation reviewed for accuracy

### Code Quality
- [ ] All new code follows project style guidelines
- [ ] No linter errors (except expected import warnings in dev)
- [ ] All functions have proper docstrings
- [ ] Error handling implemented for all new features

### Testing
- [ ] Unit tests added for noise sensor
- [ ] Unit tests added for proximity sensor tap detection
- [ ] Unit tests added for individual display plugins
- [ ] Integration tests for noise sensor MQTT discovery
- [ ] Integration tests for display plugin auto-discovery
- [ ] Integration tests for tap navigation
- [ ] All existing tests still pass
- [ ] Test coverage >= 75% for new features

### Dependencies
- [x] requirements.txt updated with sounddevice and scipy
- [ ] requirements-dev.txt updated if needed
- [ ] All dependencies compatible with Python 3.9-3.12
- [ ] No security vulnerabilities in dependencies

### Version Management
- [ ] Version number updated in setup.py/pyproject.toml
- [ ] Version number updated in __init__.py
- [ ] CHANGELOG.md date filled in for v0.2.0
- [ ] Git tag created: v0.2.0

### Release Preparation
- [ ] Release notes prepared
- [ ] GitHub release draft created
- [ ] Installation instructions verified
- [ ] Known issues documented (if any)
- [ ] Breaking changes documented (if any)

### Post-Release
- [ ] GitHub release published
- [ ] PyPI package uploaded (if applicable)
- [ ] Release announcement (if applicable)
- [ ] Monitor for issues after release

## Notes
- PM sensors deferred to v0.3.0 (hardware not available)
- Noise sensor requires microphone hardware
- Proximity tap detection requires LTR559 sensor
- Individual displays auto-rotate; tap advances to next screen

