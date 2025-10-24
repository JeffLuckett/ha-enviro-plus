# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security vulnerability in ha-enviro-plus, please report it responsibly.

### How to Report

1. **Do NOT** include vulnerability details in the issue description
2. Create a GitHub issue with the title: `[SECURITY] Brief description of issue type`
3. In the issue description, include:
   - Brief description of the issue type (e.g., "Authentication bypass", "Information disclosure")
   - Your contact information (email or GitHub username)
   - Statement: "I will provide full details privately after initial contact"
4. We will contact you directly to discuss the vulnerability privately

**Example Issue Title**: `[SECURITY] Potential authentication bypass in MQTT connection`

### What to Expect

- **Acknowledgment**: We will acknowledge receipt of your report within 48 hours
- **Initial Assessment**: We will provide an initial assessment within 7 days
- **Regular Updates**: We will provide regular updates on our progress
- **Resolution**: We aim to resolve critical vulnerabilities within 30 days

### Responsible Disclosure

We follow responsible disclosure practices:

1. **Confidentiality**: We will keep your report confidential until we have resolved the issue
2. **Coordination**: We will coordinate with you on the timing of any public disclosure
3. **Credit**: We will credit you for the discovery (unless you prefer to remain anonymous)
4. **No Legal Action**: We will not take legal action against researchers who follow these guidelines

### Scope

This security policy applies to:

- The ha-enviro-plus Python package
- Installation and uninstallation scripts
- Documentation and examples
- GitHub Actions workflows

### Out of Scope

The following are considered out of scope for security reporting:

- Issues in third-party dependencies (please report directly to those projects)
- Issues in Raspberry Pi OS or system-level components
- Issues in Home Assistant or MQTT brokers
- Social engineering attacks
- Physical attacks on hardware

### Security Best Practices

To help keep ha-enviro-plus secure:

1. **Keep Updated**: Always run the latest version
2. **Secure MQTT**: Use authentication and TLS encryption for MQTT connections
3. **Network Security**: Run on trusted networks only
4. **Access Control**: Limit physical access to the Raspberry Pi
5. **Regular Updates**: Keep the underlying OS and dependencies updated

### Security Features

ha-enviro-plus includes the following security features:

- Configuration validation on startup
- Graceful error handling to prevent crashes
- No hardcoded credentials or secrets
- Secure file permissions for configuration files
- Input validation for MQTT commands

### Contact

For security-related questions or concerns, please contact:

- **Security Issues**: Create a GitHub issue with `[SECURITY]` in the title
- **General Issues**: [GitHub Issues](https://github.com/JeffLuckett/ha-enviro-plus/issues)

Thank you for helping keep ha-enviro-plus secure!
