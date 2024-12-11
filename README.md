# README.md
# Carrus

Modern macOS package manager with MDM integration.

## About

`carrus` (Latin: wagon/carrier) is a modern, maintainable package manager for macOS, designed with MDM integration in mind. It provides robust package management with a focus on security, verification, and automation.

## Features

- 🔒 Built-in code signing verification
- 📦 Modern package management
- 🤖 MDM integration (Kandji support)
- 🔄 Automatic updates
- 🏗️ Custom package building
- ✅ Comprehensive verification

## Installation

```bash
pip install carrus
```

## Quick Start

1. Create a recipe (firefox.yaml):
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

## Documentation

- [Installation Guide](docs/installation.md)
- [Recipe Format](docs/recipes.md)
- [MDM Integration](docs/mdm_integration.md)
- [CLI Reference](docs/cli.md)
- [Security Features](docs/security.md)

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
