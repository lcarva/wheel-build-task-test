"""Find issues command for Calunga CLI."""

import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests
import typer
from rich.console import Console
from rich.panel import Panel

import yaml

console = Console()

PYPI_INDEX_URL = "https://console.redhat.com/api/pulp-content/public-calunga/mypypi/simple"


def package_version(pkg_dir: Path) -> Optional[str]:
    """Get the version of a package from its requirements.txt file."""
    pkg_name = pkg_dir.name
    req_file = pkg_dir / "requirements.txt"

    if not req_file.exists():
        return None

    with open(req_file, "r") as f:
        content = f.read()

    # Use regex to find the package version
    # Handle line continuations and clean up the version
    pattern = rf"^{re.escape(pkg_name)}==([^\\\s]+)"
    match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)

    if match:
        version = match.group(1).strip()
        # Remove any trailing backslashes and whitespace
        version = re.sub(r'\\+$', '', version).strip()
        return version
    return None


def index_version(pkg_name: str) -> Optional[str]:
    """Get the version of a package from the PyPI index."""
    url = f"{PYPI_INDEX_URL}/{pkg_name}/"

    response = requests.get(url, timeout=30)

    if response.status_code == 404:
        return "MISSING"

    if response.status_code != 200:
        return None

    # Parse HTML content to extract version
    # This is a simplified version of the yq parsing from the bash script
    html_content = response.text

    # Look for .tar.gz files and extract versions
    tar_gz_pattern = r'<a[^>]*>([^<]*\.tar\.gz)</a>'
    matches = re.findall(tar_gz_pattern, html_content)

    if not matches:
        return None

    # Extract versions from filenames
    versions = []
    for match in matches:
        # Remove .tar.gz and extract version
        filename = match.replace(".tar.gz", "")
        # Split by dash and take the last part as version
        parts = filename.split("-")
        if len(parts) > 1:
            version = parts[-1]
            versions.append(version)

    if versions:
        # Sort versions and return the latest
        versions.sort()
        return versions[-1]

    return None


def latest_built_commit_id(pkg_name: str) -> Optional[str]:
    """Get the latest built commit ID for a package from OpenShift."""
    result = subprocess.run(
        ["oc", "get", "component", pkg_name, "-o", "yaml"],
        capture_output=True,
        text=True,
        check=True
    )

    # Parse YAML output to extract lastBuiltCommit
    data = yaml.safe_load(result.stdout)
    return data.get("status", {}).get("lastBuiltCommit")


def latest_commit_id(pkg_dir: Path) -> Optional[str]:
    """Get the latest commit ID that changed a package directory."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--first-parent", "--", str(pkg_dir)],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()


def find_snapshot_for_commit_id(pkg_name: str, commit_id: str) -> Optional[str]:
    """Find snapshot for a specific commit ID."""
    result = subprocess.run(
        [
            "oc", "get", "snapshot",
            "-l", f"pac.test.appstudio.openshift.io/sha={commit_id},appstudio.openshift.io/component={pkg_name},pac.test.appstudio.openshift.io/event-type=push",
            "-o", "jsonpath={.items[0].metadata.name}"
        ],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip() if result.stdout.strip() else None


def analyze_package(pkg_dir: Path) -> Dict[str, Any]:
    """Analyze a single package for issues."""
    pkg_name = pkg_dir.name

    # Get versions
    git_version = package_version(pkg_dir)
    index_version_val = index_version(pkg_name)

    # Get commit information
    built_commit_id = latest_built_commit_id(pkg_name)
    commit_id = latest_commit_id(pkg_dir)

    # Determine issue type
    issue_type = None
    issue_description = None
    action_needed = None

    if git_version != index_version_val:
        if built_commit_id != commit_id:
            issue_type = "needs_rebuild"
            issue_description = f"Commit mismatch: built commit is {built_commit_id}, current commit is {commit_id}"
            action_needed = "rebuild"
        else:
            # Check if snapshot exists
            snapshot_name = find_snapshot_for_commit_id(pkg_name, commit_id)
            if snapshot_name:
                issue_type = "needs_release"
                issue_description = f"Build exists but not released. Snapshot: {snapshot_name}"
                action_needed = "release"
            else:
                issue_type = "unknown"
                issue_description = "Version mismatch but no clear action identified"
                action_needed = "investigate"
    else:
        issue_type = "no_issue"
        issue_description = "Versions match"
        action_needed = "none"

    return {
        "package_name": pkg_name,
        "git_version": git_version,
        "index_version": index_version_val,
        "built_commit_id": built_commit_id,
        "current_commit_id": commit_id,
        "issue_type": issue_type,
        "issue_description": issue_description,
        "action_needed": action_needed
    }


def find_packages(packages_dir: Path) -> List[Path]:
    """Find all package directories."""
    if not packages_dir.exists():
        raise typer.BadParameter(f"Packages directory not found at {packages_dir}")

    packages = []
    for item in packages_dir.iterdir():
        if item.is_dir():
            packages.append(item)

    return sorted(packages)


def find_issues(
    path: str = typer.Argument(
        default=".",
        help="Path to work on (default: current directory)"
    ),
    output_file: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for JSON results (default: stdout)"
    ),
    workers: int = typer.Option(
        5,
        "--workers",
        "-w",
        help="Number of parallel workers for package analysis (default: 5)"
    ),
) -> None:
    """Find issues with the Calunga Python index.

    This command analyzes packages to identify issues such as:
    - Version mismatches between git and index
    - Missing builds for latest commits
    - Builds that need to be released

    The output is in JSON format for easy parsing and integration.
    """
    base_path = Path(path)
    packages_dir = base_path / "packages"

    if not packages_dir.exists():
        console.print(f"[red]Error: packages directory not found at {packages_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Analyzing packages in {packages_dir} with {workers} workers[/blue]")

    packages = find_packages(packages_dir)
    results = []

    with console.status("[bold green]Analyzing packages..."):
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks
            future_to_package = {
                executor.submit(analyze_package, pkg_dir): pkg_dir
                for pkg_dir in packages
            }

            # Collect results as they complete
            for future in as_completed(future_to_package):
                pkg_dir = future_to_package[future]
                result = future.result()
                results.append(result)

    # Sort results to maintain consistent order
    results.sort(key=lambda x: x.get("package_name", ""))

    # Filter results to only show issues
    issues = [r for r in results if r.get("issue_type") != "no_issue"]

    output_data = {
        "summary": {
            "total_packages": len(results),
            "packages_with_issues": len(issues),
            "issues_by_type": {}
        },
        "issues": issues,
        "all_packages": results
    }

    # Count issues by type
    for result in results:
        issue_type = result.get("issue_type", "unknown")
        output_data["summary"]["issues_by_type"][issue_type] = output_data["summary"]["issues_by_type"].get(issue_type, 0) + 1

    # Output results
    json_output = json.dumps(output_data, indent=2)

    if output_file:
        with open(output_file, "w") as f:
            f.write(json_output)
        console.print(f"[green]Results written to {output_file}[/green]")
    else:
        console.print(json_output)

    # Show summary
    if issues:
        console.print(f"\n[red]Found {len(issues)} packages with issues[/red]")
        for issue_type, count in output_data["summary"]["issues_by_type"].items():
            if issue_type != "no_issue":
                console.print(f"  {issue_type}: {count}")
    else:
        console.print("\n[green]No issues found! All packages are up to date.[/green]")