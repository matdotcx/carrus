# src/carrus/cli.py

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from pathlib import Path
from typing import Optional
import asyncio
import yaml

app = typer.Typer(
    name="carrus",
    help="Modern macOS package manager"
)
console = Console()

# Within the download command in cli.py
@app.command()
def download(
    manifest_path: Path = typer.Argument(..., help="Path to the manifest file"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
    skip_verify: bool = typer.Option(False, "--skip-verify", help="Skip verification steps")
):
    """Download a package from its manifest."""
    try:
        from .core.manifests import Manifest
        from .core.downloader import download_file, verify_checksum
        from .core.codesign import verify_signature_requirements

        manifest = Manifest.from_yaml(manifest_path)
        output_dir = output_dir or Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)

        dest_path = output_dir / (manifest.filename or str(manifest.url).split("/")[-1])

        async def do_download():
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
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
                        debug=False
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
        console.print(f"[red]Error: {str(e)}")
        raise typer.Exit(1)

@app.command()
def verify(
    package: Path,
    team_id: Optional[str] = typer.Option(None, help="Required Team ID"),
    require_notarized: bool = typer.Option(True, help="Require notarization"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Show debug information")
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
        console.print(
            f"Notarized: {'[green]Yes' if info.notarized else '[red]No'}[/]"
        )

        if debug and info.raw_output:
            console.print("\n[bold blue]Debug Information:[/bold blue]")
            console.print(info.raw_output)

        if info.errors:
            console.print("\n[red]Errors:[/red]")
            for error in info.errors:
                console.print(f"  - {error}")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}")
        raise typer.Exit(1)

@app.command()
def repo_add(
    path: Path = typer.Argument(..., help="Path to repository"),
    name: Optional[str] = typer.Option(None, help="Repository name (optional)")
):
    """Add a manifest repository."""
    try:
        from .core.repository import RepositoryManager
        from .core.config import ensure_dirs, get_repo_dir

        _, repo_dir = ensure_dirs()
        repo_manager = RepositoryManager(repo_dir)
        metadata = repo_manager.add_repository(path, name)
        console.print(f"[green]Successfully added repository: {metadata.name}")
        console.print(f"Description: {metadata.description}")
        console.print(f"Maintainer: {metadata.maintainer}")
    except Exception as e:
        console.print(f"[red]Error adding repository: {e}")
        raise typer.Exit(1)

@app.command()
def repo_list():
    """List all repositories."""
    try:
        from .core.repository import RepositoryManager
        from .core.config import get_repo_dir

        repo_manager = RepositoryManager(get_repo_dir())
        table = repo_manager.list_manifests()
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error listing repositories: {e}")
        raise typer.Exit(1)

@app.command()
def search(
    term: str = typer.Argument(..., help="Search term"),
    category: Optional[str] = typer.Option(None, help="Limit to category")
):
    """Search for manifests."""
    try:
        from .core.repository import RepositoryManager
        from .core.config import get_repo_dir

        repo_manager = RepositoryManager(get_repo_dir())
        manifests = repo_manager.search_manifests(term, category)

        table = Table(title="Available Packages")
        table.add_column("Name", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Repository", style="yellow")
        table.add_column("Description", style="white")

        for manifest in manifests:
            table.add_row(
                manifest.name,
                manifest.category,
                manifest.repo_name,
                manifest.description or ""
            )

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error searching manifests: {e}")
        raise typer.Exit(1)

@app.command()
def check_updates(
    manifest_path: Path = typer.Argument(..., help="Path to the manifest file"),
    build_if_needed: bool = typer.Option(False, "--build", "-b", help="Build if update available")
):
    """Check for updates to a package."""
    async def async_check():
        try:
            from .core.manifests import Manifest
            from .core.updater import UpdateChecker

            manifest = Manifest.from_yaml(manifest_path)
            checker = await UpdateChecker.create_checker(manifest.type)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task_id = progress.add_task("Checking for updates...", total=None)
                update_info = await checker.check_update(manifest.version)
                progress.update(task_id, completed=True)

                if update_info:
                    console.print(f"[yellow]Update available![/yellow]")
                    console.print(f"Current version: {update_info.current_version}")
                    console.print(f"Latest version: {update_info.latest_version}")

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
                else:
                    console.print("[green]Package is up to date![/green]")

        except Exception as e:
            console.print(f"[red]Error: {str(e)}")
            raise typer.Exit(1)

    asyncio.run(async_check())

@app.command()
def build(
    manifest_path: Path = typer.Argument(..., help="Path to the manifest file"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory")
):
    """Build a package."""
    async def async_build():
        try:
            from .core.manifests import Manifest
            from .core.builder import build_package

            manifest = Manifest.from_yaml(manifest_path)
            console.print(f"[blue]Loading manifest: {manifest_path}[/blue]")

            # Get the actual DMG file path
            downloaded_file = Path(manifest.filename)
            if not downloaded_file.exists():
                console.print("[red]Error: Downloaded file not found. Did you run download first?[/red]")
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
                console=console
            ) as progress:
                result = await build_package(downloaded_file, build_config, progress)

                if result.success:
                    console.print(f"[green]Successfully built package: {result.output_path}[/green]")
                else:
                    console.print("[red]Build failed![/red]")
                    for error in result.errors:
                        console.print(f"[red]  {error}[/red]")
                    raise typer.Exit(1)

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            raise typer.Exit(1)

    asyncio.run(async_build())

@app.command()
def build_mdm(
    manifest_path: Path = typer.Argument(..., help="Path to the manifest file"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory")
):
    """Build an MDM-ready package."""
    async def async_build():
        try:
            from .core.manifests import Manifest
            from .core.builder import build_package
            from .core.updater import MDMPackageBuilder

            manifest = Manifest.from_yaml(manifest_path)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                # First build the regular package
                task_id = progress.add_task("Building application...", total=None)
                
                # Get the actual DMG file path
                downloaded_file = Path(manifest.filename)
                if not downloaded_file.exists():
                    console.print("[red]Error: Downloaded file not found. Did you run download first?[/red]")
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
                    manifest.mdm.kandji if manifest.mdm else {}
                )

                progress.update(task_id, completed=True)
                console.print(f"[green]Successfully created MDM package: {pkg_path}")

        except Exception as e:
            console.print(f"[red]Error: {str(e)}")
            raise typer.Exit(1)

    asyncio.run(async_build())

if __name__ == "__main__":
    app()
