# src/carrus/cli.py

import asyncio
import datetime
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from typing_extensions import Annotated

# CLI argument/option definitions
MANIFEST_PATH = typer.Argument(..., help="Path to the manifest file")
OUTPUT_DIR = typer.Option(None, "--output", "-o", help="Output directory")
SKIP_VERIFY = typer.Option(False, "--skip-verify", help="Skip verification steps")
BUILD_IF_NEEDED = typer.Option(False, "--build", "-b", help="Build if update available")
REPO_PATH = typer.Argument(..., help="Path to repository")
REPO_NAME = typer.Option(None, help="Repository name (optional)")
TEAM_ID = typer.Option(None, help="Required Team ID")
REQUIRE_NOTARIZED = typer.Option(True, help="Require notarization")
DEBUG = typer.Option(False, "--debug", "-d", help="Show debug information")
CATEGORY_FILTER = typer.Option(None, help="Limit to category")
SEARCH_TERM = typer.Argument(..., help="Search term")

# Notification options
NOTIFICATION_ENABLED = typer.Option(
    True, help="Enable or disable notifications"
)
NOTIFICATION_METHOD = typer.Option(
    "cli", "--method", "-m", help="Notification method: cli, system, email, github, or slack"
)
NOTIFICATION_EMAIL = typer.Option(None, "--email", help="Email address for notifications")
NOTIFICATION_INTERVAL = typer.Option(24, "--interval", "-i", help="Check interval in hours")
NOTIFICATION_GITHUB_TOKEN = typer.Option(
    None, "--github-token", help="GitHub token for authentication"
)
NOTIFICATION_GITHUB_REPO = typer.Option(
    None, "--github-repo", help="GitHub repository for notifications (owner/repo)"
)
NOTIFICATION_GITHUB_LABEL = typer.Option(
    "update-available", "--github-label", help="GitHub issue label"
)
NOTIFICATION_SLACK_WEBHOOK = typer.Option(
    None, "--slack-webhook", help="Slack webhook URL for sending notifications"
)
NOTIFICATION_SLACK_CHANNEL = typer.Option(
    None, "--slack-channel", help="Slack channel to send notifications to (optional)"
)
NOTIFICATION_SLACK_USERNAME = typer.Option(
    "Carrus Update Bot", "--slack-username", help="Username for Slack notifications"
)

app = typer.Typer(name="carrus", help="Modern macOS package manager")
console = Console()


# Within the download command in cli.py
@app.command()
def download(
    manifest_path: Path = MANIFEST_PATH,
    output_dir: Optional[Path] = OUTPUT_DIR,
    skip_verify: bool = SKIP_VERIFY,
):
    """Download a package from its manifest."""
    try:
        from .core.codesign import verify_signature_requirements
        from .core.downloader import download_file, verify_checksum
        from .core.manifests import Manifest

        manifest = Manifest.from_yaml(manifest_path)
        output_dir = output_dir or Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)

        dest_path = output_dir / (manifest.filename or str(manifest.url).split("/")[-1])

        async def do_download():
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                await download_file(str(manifest.url), dest_path, progress)

            console.print(f"Successfully downloaded to {dest_path}")

            if not skip_verify:
                # Verify checksum
                if manifest.checksum:
                    if verify_checksum(dest_path, manifest.checksum):
                        console.print("[green]Checksum verification passed!")
                    else:
                        console.print("[red]Warning: Checksum verification failed!")
                        raise typer.Exit(1)

                # Verify code signing if requirements specified
                if manifest.code_sign:
                    passed, errors = verify_signature_requirements(
                        dest_path,
                        required_team_id=manifest.code_sign.team_id,
                        require_notarized=manifest.code_sign.require_notarized,
                        debug=False,
                    )
                    if passed:
                        console.print("[green]Code signing verification passed!")
                    else:
                        console.print("[red]Code signing verification failed!")
                        for error in errors:
                            console.print(f"[red]  {error}")
                        raise typer.Exit(1)

        asyncio.run(do_download())

    except Exception as e:
        raise typer.Exit(1) from e


@app.command()
def verify(
    package: Path = MANIFEST_PATH,
    team_id: Optional[str] = TEAM_ID,
    require_notarized: bool = REQUIRE_NOTARIZED,
    debug: bool = DEBUG,
):
    """Verify a package's signature and notarization."""
    try:
        from .core.codesign import verify_codesign

        if not package.exists():
            console.print(f"[red]Error: File {package} not found")
            raise typer.Exit(1)

        info = verify_codesign(package, debug=debug)

        console.print("\n[bold]Code Signing Information:[/bold]")
        console.print(f"Signed: {'[green]Yes' if info.signed else '[red]No'}[/]")
        if info.team_id:
            console.print(f"Team ID: {info.team_id}")
        if info.authority:
            console.print("Signing Authorities:")
            for auth in info.authority:
                console.print(f"  - {auth}")
        console.print(f"Notarized: {'[green]Yes' if info.notarized else '[red]No'}[/]")

        if debug and info.raw_output:
            console.print("\n[bold blue]Debug Information:[/bold blue]")
            console.print(info.raw_output)

        if info.errors:
            console.print("\n[red]Errors:[/red]")
            for error in info.errors:
                console.print(f"  - {error}")

    except Exception as e:
        raise typer.Exit(1) from e


@app.command()
def repo_add(path: Path = REPO_PATH, name: Optional[str] = REPO_NAME):
    """Add a manifest repository."""
    try:
        from .core.config import ensure_dirs
        from .core.repository import RepositoryManager

        _, repo_dir = ensure_dirs()
        repo_manager = RepositoryManager(repo_dir)
        metadata = repo_manager.add_repository(path, name)
        console.print(f"[green]Successfully added repository: {metadata.name}")
        console.print(f"Description: {metadata.description}")
        console.print(f"Maintainer: {metadata.maintainer}")
    except Exception as e:
        raise typer.Exit(1) from e


@app.command()
def repo_list():
    """List all repositories."""
    try:
        from .core.config import get_repo_dir
        from .core.repository import RepositoryManager

        repo_manager = RepositoryManager(get_repo_dir())
        table = repo_manager.list_manifests()
        console.print(table)
    except Exception as e:
        raise typer.Exit(1) from e


@app.command()
def search(
    term: str = SEARCH_TERM,
    category: Optional[str] = CATEGORY_FILTER,
):
    """Search for manifests."""
    try:
        from .core.config import get_repo_dir
        from .core.repository import RepositoryManager

        repo_manager = RepositoryManager(get_repo_dir())
        manifests = repo_manager.search_manifests(term, category)

        table = Table(title="Available Packages")
        table.add_column("Name", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Repository", style="yellow")
        table.add_column("Description", style="white")

        for manifest in manifests:
            table.add_row(
                manifest.name, manifest.category, manifest.repo_name, manifest.description or ""
            )

        console.print(table)
    except Exception as e:
        raise typer.Exit(1) from e


@app.command()
def check_updates(
    manifest_path: Path = MANIFEST_PATH,
    build_if_needed: bool = BUILD_IF_NEEDED,
    notify: bool = typer.Option(
        False, "--notify", "-n", help="Send notification if update available"
    ),
):
    """Check for updates to a package."""

    async def async_check():
        try:
            from .core.config import get_config_dir, get_default_config, load_config, save_config
            from .core.manifests import Manifest
            from .core.notifications import Notification, NotificationService
            from .core.updater import UpdateChecker

            # Load configuration for notifications if needed
            config = None
            if notify:
                config_dir = get_config_dir()
                config_path = config_dir / "config.yaml"

                if config_path.exists():
                    config = load_config(config_path)
                else:
                    config = get_default_config()
                    save_config(config, config_path)

            manifest = Manifest.from_yaml(manifest_path)
            checker = await UpdateChecker.create_checker(manifest.type)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task_id = progress.add_task("Checking for updates...", total=None)
                update_info = await checker.check_update(manifest.version)
                progress.update(task_id, completed=True)

                if update_info:
                    console.print("[yellow]Update available![/yellow]")
                    console.print(f"Current version: {update_info.current_version}")
                    console.print(f"Latest version: {update_info.latest_version}")

                    # Send notification if requested
                    if notify and config:
                        notification_service = NotificationService(config)
                        notification = Notification(
                            title="Update Available",
                            message=f"A new version of {manifest.name} is available.",
                            package_name=manifest.name,
                            current_version=update_info.current_version,
                            new_version=update_info.latest_version,
                        )
                        await notification_service.provider.notify(notification)
                        console.print("[green]Notification sent[/green]")

                    if build_if_needed:
                        # Update manifest with new version
                        manifest.version = update_info.latest_version
                        manifest.url = update_info.download_url
                        manifest.checksum = None  # Will be verified after download

                        # Write updated manifest
                        with open(manifest_path, "w") as f:
                            yaml.dump(manifest.dict(), f)

                        # Build new version
                        console.print("\n[green]Building new version...[/green]")
                        await build_mdm(manifest_path)

                        # Record the update in the database if we have config
                        if config:
                            try:
                                from .core.database import Database
                                from .core.updater import VersionTracker

                                db = Database(Path(config.db_path))
                                version_tracker = VersionTracker(db)

                                # Check if package exists in database
                                package = db.get_package_by_name(manifest.name)
                                if not package:
                                    # Add the package to the database
                                    pkg_id = db.add_package(
                                        name=manifest.name,
                                        version=update_info.latest_version,
                                        status="installed",
                                    )

                                    # Add the version
                                    db.add_package_version(
                                        package_id=pkg_id,
                                        version=update_info.latest_version,
                                        url=update_info.download_url,
                                        is_installed=True,
                                    )
                                else:
                                    # Record the version
                                    version_tracker.record_version(
                                        package_name=manifest.name,
                                        version=update_info.latest_version,
                                        download_url=update_info.download_url,
                                    )

                                    # Mark as installed
                                    version_tracker.mark_version_installed(
                                        package_name=manifest.name,
                                        version=update_info.latest_version,
                                    )
                            except Exception as db_error:
                                console.print(
                                    f"[yellow]Warning: Could not record update in database: {db_error}[/yellow]"
                                )
                else:
                    console.print("[green]Package is up to date![/green]")

        except Exception as e:
            console.print(f"[red]Error checking for updates: {e}[/red]")
            raise typer.Exit(1) from e

    asyncio.run(async_check())


@app.command()
def build(
    manifest_path: Path = MANIFEST_PATH,
    output_dir: Optional[Path] = OUTPUT_DIR,
):
    """Build a package."""

    async def async_build():
        try:
            from .core.builder import build_package
            from .core.manifests import Manifest

            manifest = Manifest.from_yaml(manifest_path)
            console.print(f"[blue]Loading manifest: {manifest_path}[/blue]")

            # Get the actual DMG file path
            downloaded_file = Path(manifest.filename)
            if not downloaded_file.exists():
                console.print(
                    "[red]Error: Downloaded file not found. Did you run download first?[/red]"
                )
                raise typer.Exit(1)

            build_config = manifest.get_build_config()
            if not build_config:
                console.print("[red]Error: Manifest does not contain build configuration[/red]")
                raise typer.Exit(1)

            if output_dir:
                build_config.destination = str(output_dir)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                result = await build_package(downloaded_file, build_config, progress)

                if result.success:
                    console.print(
                        f"[green]Successfully built package: {result.output_path}[/green]"
                    )
                else:
                    console.print("[red]Build failed![/red]")
                    for error in result.errors:
                        console.print(f"[red]  {error}[/red]")
                    raise typer.Exit(1)

        except Exception as e:
            raise typer.Exit(1) from e

    asyncio.run(async_build())


@app.command()
def build_mdm(
    manifest_path: Path = MANIFEST_PATH,
    output_dir: Optional[Path] = OUTPUT_DIR,
):
    """Build an MDM-ready package."""

    async def async_build():
        try:
            from .core.builder import build_package
            from .core.manifests import Manifest
            from .core.updater import MDMPackageBuilder

            manifest = Manifest.from_yaml(manifest_path)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                # First build the regular package
                task_id = progress.add_task("Building application...", total=None)

                # Get the actual DMG file path
                downloaded_file = Path(manifest.filename)
                if not downloaded_file.exists():
                    console.print(
                        "[red]Error: Downloaded file not found. Did you run download first?[/red]"
                    )
                    raise typer.Exit(1)

                build_config = manifest.get_build_config()
                if not build_config:
                    console.print("[red]Error: Manifest does not contain build configuration[/red]")
                    raise typer.Exit(1)

                if output_dir:
                    build_config.destination = str(output_dir)

                build_result = await build_package(downloaded_file, build_config, progress)

                if not build_result.success:
                    console.print("[red]Build failed![/red]")
                    for error in build_result.errors:
                        console.print(f"[red]  {error}[/red]")
                    raise Exception("Failed to build application package")

                progress.update(task_id, completed=True)

                # Now create MDM package
                task_id = progress.add_task("Creating MDM package...", total=None)

                mdm_builder = MDMPackageBuilder(output_dir or Path.cwd())
                pkg_path = await mdm_builder.build_kandji_package(
                    build_result.output_path,
                    manifest.name,
                    manifest.version,
                    manifest.mdm.kandji if manifest.mdm else {},
                )

                progress.update(task_id, completed=True)
                console.print(f"[green]Successfully created MDM package: {pkg_path}")

        except Exception as e:
            raise typer.Exit(1) from e

    asyncio.run(async_build())


# Create a notification subcommand group
notifications_app = typer.Typer(name="notifications", help="Manage update notifications")
app.add_typer(notifications_app)


@notifications_app.command("check")
def check_for_notifications():
    """Check for available updates and send notifications."""

    async def async_check():
        try:
            from .core.config import get_config_dir, get_default_config, load_config, save_config
            from .core.notifications import NotificationService

            config_dir = get_config_dir()
            config_path = config_dir / "config.yaml"

            # Load or create config
            if config_path.exists():
                config = load_config(config_path)
            else:
                config = get_default_config()
                save_config(config, config_path)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task_id = progress.add_task("Checking for updates...", total=None)

                # Create notification service
                service = NotificationService(config)

                # Check for updates and send notifications
                notification_count = await service.notify_updates()

                progress.update(task_id, completed=True)

                # Save updated last check time
                save_config(config, config_path)

                if notification_count > 0:
                    console.print(
                        f"[green]Sent {notification_count} update notification(s)[/green]"
                    )
                else:
                    console.print("[green]No updates available[/green]")

        except Exception as e:
            console.print(f"[red]Error checking for updates: {e}[/red]")
            raise typer.Exit(1) from e

    asyncio.run(async_check())


@notifications_app.command("configure")
def configure_notifications(
    enabled: Annotated[bool, typer.Option(True, "--enabled/--disabled", help="Enable or disable notifications")],
    method: Annotated[str, NOTIFICATION_METHOD],
    email: Annotated[Optional[str], NOTIFICATION_EMAIL] = None,
    interval: Annotated[int, NOTIFICATION_INTERVAL] = 24,
    github_token: Annotated[Optional[str], NOTIFICATION_GITHUB_TOKEN] = None,
    github_repo: Annotated[Optional[str], NOTIFICATION_GITHUB_REPO] = None,
    github_label: Annotated[Optional[str], NOTIFICATION_GITHUB_LABEL] = "update-available",
    slack_webhook: Annotated[Optional[str], NOTIFICATION_SLACK_WEBHOOK] = None,
    slack_channel: Annotated[Optional[str], NOTIFICATION_SLACK_CHANNEL] = None,
    slack_username: Annotated[Optional[str], NOTIFICATION_SLACK_USERNAME] = "Carrus Update Bot",
):
    """Configure notification settings."""
    try:
        from .core.config import (
            NotificationConfig,
            get_config_dir,
            get_default_config,
            load_config,
            save_config,
        )

        config_dir = get_config_dir()
        config_path = config_dir / "config.yaml"

        # Load or create config
        if config_path.exists():
            config = load_config(config_path)
        else:
            config = get_default_config()

        # Validate method
        if method not in ["cli", "system", "email", "github", "slack"]:
            console.print(
                "[red]Error: Invalid notification method. Must be cli, system, email, github, or slack.[/red]"
            )
            raise typer.Exit(1)

        # Validate email if using email notifications
        if method == "email" and not email:
            console.print("[red]Error: Email address required for email notifications.[/red]")
            raise typer.Exit(1)

        # Validate GitHub settings if using GitHub notifications
        if method == "github":
            if not github_token:
                console.print("[red]Error: GitHub token required for GitHub notifications.[/red]")
                raise typer.Exit(1)
            if not github_repo:
                console.print(
                    "[red]Error: GitHub repository required for GitHub notifications.[/red]"
                )
                raise typer.Exit(1)

        # Validate Slack settings if using Slack notifications
        if method == "slack" and not slack_webhook:
            console.print("[red]Error: Slack webhook URL required for Slack notifications.[/red]")
            raise typer.Exit(1)

        # Update notification config
        config.notifications = NotificationConfig(
            enabled=enabled,
            method=method,
            email=email,
            check_interval=interval,
            notify_on_startup=config.notifications.notify_on_startup,
            last_check=config.notifications.last_check,
            github_token=github_token,
            github_repo=github_repo,
            github_issue_label=github_label,
            slack_webhook_url=slack_webhook,
            slack_channel=slack_channel,
            slack_username=slack_username,
        )

        # Save config
        save_config(config, config_path)

        console.print("[green]Notification settings updated successfully[/green]")
        console.print(f"Notifications: {'Enabled' if enabled else 'Disabled'}")
        console.print(f"Method: {method}")
        if method == "email":
            console.print(f"Email: {email}")
        elif method == "github":
            console.print(f"GitHub Repository: {github_repo}")
            console.print(f"GitHub Issue Label: {github_label}")
            console.print(f"GitHub Token: {'Configured' if github_token else 'Not configured'}")
        elif method == "slack":
            console.print(f"Slack Webhook: {'Configured' if slack_webhook else 'Not configured'}")
            if slack_channel:
                console.print(f"Slack Channel: {slack_channel}")
            console.print(f"Slack Username: {slack_username}")
        console.print(f"Check interval: {interval} hours")

    except Exception as e:
        console.print(f"[red]Error configuring notifications: {e}[/red]")
        raise typer.Exit(1) from e


@notifications_app.command("status")
def notification_status():
    """Show current notification settings."""
    try:
        from .core.config import get_config_dir, get_default_config, load_config

        config_dir = get_config_dir()
        config_path = config_dir / "config.yaml"

        # Load or create config
        if config_path.exists():
            config = load_config(config_path)
        else:
            config = get_default_config()
            console.print("[yellow]No configuration found. Using default settings.[/yellow]")

        notifications = config.notifications

        console.print("[bold]Notification Settings:[/bold]")
        console.print(
            f"Enabled: [{'green' if notifications.enabled else 'red'}]{notifications.enabled}[/]"
        )
        console.print(f"Method: {notifications.method}")
        if notifications.method == "email":
            console.print(f"Email: {notifications.email or 'Not configured'}")
        elif notifications.method == "github":
            console.print(f"GitHub Repository: {notifications.github_repo or 'Not configured'}")
            console.print(f"GitHub Issue Label: {notifications.github_issue_label}")
            console.print(
                f"GitHub Token: {'Configured' if notifications.github_token else 'Not configured'}"
            )
        elif notifications.method == "slack":
            console.print(
                f"Slack Webhook: {'Configured' if notifications.slack_webhook_url else 'Not configured'}"
            )
            if notifications.slack_channel:
                console.print(f"Slack Channel: {notifications.slack_channel}")
            console.print(f"Slack Username: {notifications.slack_username}")
        console.print(f"Check interval: {notifications.check_interval} hours")

        if notifications.last_check:
            try:
                last_check = datetime.datetime.fromisoformat(notifications.last_check)
                console.print(f"Last check: {last_check.strftime('%Y-%m-%d %H:%M:%S')}")

                # Calculate next check
                next_check = last_check + datetime.timedelta(hours=notifications.check_interval)
                console.print(f"Next check: {next_check.strftime('%Y-%m-%d %H:%M:%S')}")

            except (ValueError, TypeError):
                console.print("Last check: Never")
        else:
            console.print("Last check: Never")

    except Exception as e:
        console.print(f"[red]Error retrieving notification status: {e}[/red]")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
