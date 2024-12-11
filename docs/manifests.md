# docs/recipes.md
# Carrus Recipes

## Overview

Carrus recipes are YAML files that define how to download, verify, and package software for macOS. They're designed to be readable, maintainable, and secure.

## Basic Recipe Structure

```yaml
name: Firefox
version: "123.0"
type: "firefox"
url: "https://download-installer.cdn.mozilla.net/pub/firefox/releases/123.0/mac/en-US/Firefox%20123.0.dmg"
filename: "Firefox-123.0.dmg"
checksum: "80321c06df972dcf7d346d1137ca0d31be8988fdcf892702da77a43f4bb8a8f1"

# Code signing verification
code_sign:
  team_id: "43AQ936H96"
  require_notarized: true

# Build configuration
build:
  type: "app_dmg"
  destination: "/Applications"
  preserve_temp: false

# MDM configuration (optional)
mdm:
  kandji:
    display_name: "Mozilla Firefox"
    description: "Firefox web browser"
    category: "Browsers"
    developer: "Mozilla"
    minimum_os_version: "11.0"
    uninstallable: true
```

## Fields

### Required Fields
- `name`: Application name
- `version`: Version string
- `type`: Recipe type (for update checking)
- `url`: Download URL
- `filename`: Output filename

### Optional Fields
- `checksum`: SHA256 checksum for verification
- `code_sign`: Code signing requirements
- `build`: Build configuration
- `mdm`: MDM-specific configuration

## Recipe Types

Built-in recipe types:
- `firefox`: Firefox browser (supports auto-updates)
- `app_dmg`: Generic DMG containing an app
- `pkg`: Standard PKG installer
- `zip`: ZIP archive containing an app

## Code Signing Verification

```yaml
code_sign:
  team_id: "43AQ936H96"  # Required Team ID
  require_notarized: true  # Require notarization
  authorities:  # Optional specific authorities
    - "Developer ID Application: Mozilla Corporation (43AQ936H96)"
```

## Build Configuration

```yaml
build:
  type: "app_dmg"  # Build type
  destination: "/Applications"  # Install location
  preserve_temp: false  # Keep temp files
  customize:  # Optional customization
    - delete: ["*.DS_Store"]
    - replace: 
        file: "firefox.cfg"
        with: "configs/firefox.cfg"
```

## MDM Integration

### Kandji Configuration
```yaml
mdm:
  kandji:
    display_name: "Mozilla Firefox"
    description: "Firefox web browser"
    category: "Browsers"
    developer: "Mozilla"
    minimum_os_version: "11.0"
    uninstallable: true
    preinstall_script: |
      #!/bin/zsh
      # Close Firefox if running
      pkill -x "Firefox" || true
    postinstall_script: |
      #!/bin/zsh
      # Set up policies
      defaults write /Applications/Firefox.app/Contents/Info.plist LSMinimumSystemVersion "11.0"
```

## Example Recipes

### Basic Firefox Recipe
```yaml
name: Firefox
version: "123.0"
type: "firefox"
url: "https://download-installer.cdn.mozilla.net/pub/firefox/releases/123.0/mac/en-US/Firefox%20123.0.dmg"
filename: "Firefox-123.0.dmg"
code_sign:
  team_id: "43AQ936H96"
build:
  type: "app_dmg"
```

### Custom App Recipe
```yaml
name: CustomApp
version: "1.0"
type: "app_dmg"
url: "https://example.com/CustomApp.dmg"
filename: "CustomApp.dmg"
build:
  type: "app_dmg"
  customize:
    - replace:
        file: "config.json"
        with: "custom_config.json"
```

## Working with Recipes

### Command Line Usage
```bash
# Download and verify
carrus download firefox.yaml

# Check for updates
carrus check-updates firefox.yaml

# Build MDM package
carrus build-mdm firefox.yaml

# Verify existing package
carrus verify Firefox.dmg
```

## Recipe Best Practices

1. Always include code signing requirements
2. Use checksums when possible
3. Specify explicit versions
4. Include MDM configuration for managed deployments
5. Document any customizations
6. Use appropriate recipe types for auto-updates
