
[![CI](https://github.com/matdotcx/carrus/actions/workflows/ci.yml/badge.svg)](https://github.com/matdotcx/carrus/actions/workflows/ci.yml)

# README.md
# Carrus 🛺 

Modern macOS package manager with MDM integration.

## About

`carrus` (Latin: wagon/carrier) is a modern, maintainable package manager for macOS, designed with MDM integration in mind. It provides robust package management with a focus on security, verification, and automation.

## Features

- 🔒 Built-in code signing verification
- 📦 Modern package management
- 🤖 MDM integration (Kandji support)
- 🔄 Automatic updates with notifications
- 🏗️ Custom package building
- ✅ Comprehensive verification
- 🔔 Multi-channel notifications (CLI, System, Email, GitHub, Slack)

## Installation

carrus is currently under development, and so is expected to be buggy. It's suggested install directly from source until further notice; 

```
# Clone the repository
git clone https://github.com/matdotcx/carrus.git
cd carrus

# Create and activate a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e .
```

## Quick Start

1. Create a manifest (firefox.yaml):
```yaml
name: Firefox
version: "123.0"
type: "firefox"
url: "https://download-installer.cdn.mozilla.net/pub/firefox/releases/123.0/mac/en-US/Firefox%20123.0.dmg"
filename: "Firefox-123.0.dmg"
code_sign:
  team_id: "43AQ936H96"
  require_notarized: true
build:
  type: "app_dmg"
  destination: "/Applications"
```

2. Download and verify:
```bash
carrus download firefox.yaml
```

3. Build for MDM:
```bash
carrus build-mdm firefox.yaml
```

4. Configure notifications:
```bash
carrus notifications configure --method slack --slack-webhook https://hooks.slack.com/services/XXX/YYY/ZZZ --slack-channel "#software-updates"
```

## Notification Support

Carrus supports multiple notification channels:

- **CLI**: Simple command-line notifications
- **System**: Native macOS notifications
- **Email**: Email notifications
- **GitHub**: Creates/updates GitHub issues for available updates
- **Slack**: Rich Slack notifications

For GitHub Actions integration and advanced Slack setup, see [Slack Notifications Documentation](docs/slack-notifications.md).

