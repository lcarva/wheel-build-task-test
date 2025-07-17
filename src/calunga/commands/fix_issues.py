"""Fix issues command for Calunga CLI."""

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def mark_package_for_rebuild(package_name: str) -> None:
    """Mark a package for rebuild by adding a comment to its argfile.conf.

    Args:
        package_name: Name of the package to mark for rebuild
    """
    argfile_path = Path(f"packages/{package_name}/argfile.conf")

    # Read current content
    with open(argfile_path, "r") as f:
        content = f.read()

    # Remove any existing force rebuild comments
    lines = content.splitlines()
    lines = [line for line in lines if not line.startswith("# Add comment to force rebuild")]

    # Add new force rebuild comment with current timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")
    lines.append(f"# Add comment to force rebuild, {timestamp}")

    # Write back to file
    with open(argfile_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def commit_and_push_changes(package_names: List[str]) -> str:
    """Commit and push changes for the modified packages.

    Args:
        package_names: List of package names that were modified

    Returns:
        The commit SHA of the pushed commit
    """
    # Add all modified argfile.conf files
    for package_name in package_names:
        argfile_path = f"packages/{package_name}/argfile.conf"
        subprocess.run(["git", "add", argfile_path], check=True, capture_output=True, text=True)

    # Create commit
    commit_message = f"Mark packages for rebuild: {', '.join(package_names)}"
    subprocess.run(
        ["git", "commit", "-m", commit_message, "--signoff"],
        check=True, capture_output=True, text=True
    )

    # Get the commit SHA
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True
    )
    commit_sha = result.stdout.strip()

    # Push the commit
    subprocess.run(["git", "push"], check=True, capture_output=True, text=True)

    return commit_sha


def wait_for_commit_checks(commit_sha: str, max_wait_minutes: int = 5) -> bool:
    """Wait for commit checks to appear and complete.

    Args:
        commit_sha: The commit SHA to monitor
        max_wait_minutes: Maximum time to wait for checks to appear

    Returns:
        True if all checks passed, False otherwise
    """
    console.print(f"[blue]Waiting for commit checks to appear for {commit_sha[:8]}...[/blue]")

    # Wait for checks to appear (up to max_wait_minutes)
    start_time = time.time()
    checks_found = False

    while time.time() - start_time < max_wait_minutes * 60:
        # Check if any checks exist for this commit
        result = subprocess.run(
            ["gh", "api", f"repos/lcarva/calunga/commits/{commit_sha}/check-runs"],
            check=True, capture_output=True, text=True
        )

        checks_data = json.loads(result.stdout)
        if checks_data.get("check_runs") and len(checks_data["check_runs"]) > 0:
            checks_found = True
            console.print(f"[green]Found {len(checks_data['check_runs'])} checks for commit[/green]")
            break

        console.print("[yellow]No checks found yet, waiting...[/yellow]")
        time.sleep(30)  # Wait 30 seconds before checking again

    if not checks_found:
        console.print(f"[red]Error: No commit checks appeared after {max_wait_minutes} minutes[/red]")
        return False

    # Now wait for all checks to complete
    console.print("[blue]Waiting for all checks to complete...[/blue]")

    while True:
        result = subprocess.run(
            ["gh", "api", f"repos/lcarva/calunga/commits/{commit_sha}/check-runs"],
            check=True, capture_output=True, text=True
        )

        checks_data = json.loads(result.stdout)
        check_runs = checks_data.get("check_runs", [])

        if not check_runs:
            console.print("[yellow]No checks found, waiting...[/yellow]")
            time.sleep(30)
            continue

        # Check status of all checks
        all_completed = True
        all_successful = True

        for check in check_runs:
            status = check.get("status", "unknown")
            conclusion = check.get("conclusion", "unknown")
            name = check.get("name", "unknown")

            if status == "queued" or status == "in_progress":
                all_completed = False
                console.print(f"[yellow]Check '{name}' still running (status: {status})[/yellow]")
            elif conclusion == "failure" or conclusion == "cancelled":
                all_successful = False
                console.print(f"[red]Check '{name}' failed (conclusion: {conclusion})[/red]")
            elif conclusion == "success":
                console.print(f"[green]Check '{name}' passed[/green]")
            else:
                console.print(f"[yellow]Check '{name}' has unexpected conclusion: {conclusion}[/yellow]")

        if all_completed:
            if all_successful:
                console.print("[green]All checks passed successfully![/green]")
                return True
            else:
                console.print("[red]Some checks failed[/red]")
                return False

        time.sleep(30)  # Wait 30 seconds before checking again


def find_snapshot_for_commit_id(package_name: str, commit_id: str) -> str:
    """Find the snapshot name for a given package and commit ID.

    Args:
        package_name: Name of the package
        commit_id: The commit ID to search for

    Returns:
        The snapshot name for the given package and commit

    Raises:
        subprocess.CalledProcessError: If the oc command fails
        ValueError: If no snapshot is found
    """
    # Construct the label selector
    label_selector = (
        f"pac.test.appstudio.openshift.io/sha={commit_id},"
        f"appstudio.openshift.io/component={package_name},"
        f"pac.test.appstudio.openshift.io/event-type=push"
    )

    # Run the oc command to get the snapshot
    result = subprocess.run(
        [
            "oc", "get", "snapshot",
            "-l", label_selector,
            "-o", "jsonpath={.items[0].metadata.name}"
        ],
        check=True, capture_output=True, text=True
    )

    snapshot_name = result.stdout.strip()
    if not snapshot_name:
        raise ValueError(f"No snapshot found for package {package_name} and commit {commit_id}")

    return snapshot_name


def create_release_for_snapshot(snapshot_name: str) -> str:
    """Create a release for a given snapshot.

    Args:
        snapshot_name: Name of the snapshot to release

    Returns:
        The name of the created release

    Raises:
        subprocess.CalledProcessError: If the oc command fails
    """
    # Create the release YAML content
    release_yaml = f"""apiVersion: appstudio.redhat.com/v1alpha1
kind: Release
metadata:
  generateName: managed-
spec:
  releasePlan: test-calunga
  snapshot: {snapshot_name}
  data:
    releaseNotes:
    references: ""
    synopsis: ""
    topic: ""
    description: ""
"""

    # Create the release using oc
    result = subprocess.run(
        ["oc", "create", "-f", "-"],
        input=release_yaml,
        text=True,
        check=True,
        capture_output=True
    )

    # Extract the release name from the output
    # Output format: "release.appstudio.redhat.com/managed-xxxxx created"
    output_lines = result.stdout.strip().split('\n')
    for line in output_lines:
        if 'release.appstudio.redhat.com/' in line:
            release_name = line.split('/')[-1].split()[0]
            return release_name

    raise ValueError("Could not extract release name from oc create output")


def wait_for_release_completion(release_name: str, max_wait_minutes: int = 10) -> bool:
    """Wait for a release to complete.

    Args:
        release_name: Name of the release to monitor
        max_wait_minutes: Maximum time to wait for completion

    Returns:
        True if release completed successfully, False otherwise

    Raises:
        subprocess.CalledProcessError: If the oc command fails
    """
    console.print(f"[blue]Waiting for release {release_name} to complete...[/blue]")

    start_time = time.time()
    while time.time() - start_time < max_wait_minutes * 60:
        # Get the release status
        result = subprocess.run(
            [
                "oc", "get", "release", release_name,
                "-o", "jsonpath={.status.conditions[?(@.type==\"Released\")].reason}"
            ],
            check=True, capture_output=True, text=True
        )

        reason = result.stdout.strip()

        if reason == "Succeeded":
            console.print(f"[green]✓ Release {release_name} completed successfully[/green]")
            return True
        elif reason == "Failed":
            console.print(f"[red]✗ Release {release_name} failed[/red]")
            return False
        else:
            # Reason is empty or unknown, still waiting
            console.print(f"[yellow]Release {release_name} still in progress...[/yellow]")
            time.sleep(30)  # Wait 30 seconds before checking again

    console.print(f"[red]✗ Release {release_name} did not complete within {max_wait_minutes} minutes[/red]")
    return False


def process_batch_release(release_issues: List[Dict[str, Any]]) -> None:
    """Process a batch of packages that need releasing.

    This function:
    1. Finds the snapshot for each package using its built_commit_id
    2. Creates a release for each snapshot
    3. Waits for all releases to complete
    4. Verifies all releases succeeded

    Args:
        release_issues: List of release issue dictionaries containing package_name and built_commit_id
    """
    if not release_issues:
        console.print("[yellow]No packages to release[/yellow]")
        return

    console.print(f"[blue]Processing {len(release_issues)} packages for release: {', '.join([issue['package_name'] for issue in release_issues])}[/blue]")

    # Step 1: Find snapshots and create releases
    console.print("[blue]Finding snapshots and creating releases...[/blue]")
    releases_created = []
    for issue in release_issues:
        package_name = issue["package_name"]
        built_commit_id = issue["built_commit_id"]

        try:
            # Find the snapshot
            snapshot_name = find_snapshot_for_commit_id(package_name, built_commit_id)
            console.print(f"[green]✓ Found snapshot {snapshot_name} for {package_name}[/green]")

            # Create the release
            release_name = create_release_for_snapshot(snapshot_name)
            console.print(f"[green]✓ Created release {release_name} for {package_name}[/green]")

            releases_created.append({
                "package_name": package_name,
                "release_name": release_name,
                "snapshot_name": snapshot_name
            })

        except Exception as e:
            console.print(f"[red]✗ Failed to process {package_name}: {e}[/red]")
            raise

    # Step 2: Wait for all releases to complete
    console.print(f"[blue]Waiting for {len(releases_created)} releases to complete...[/blue]")

    all_successful = True
    for release_info in releases_created:
        package_name = release_info["package_name"]
        release_name = release_info["release_name"]

        try:
            success = wait_for_release_completion(release_name)
            if success:
                console.print(f"[green]✓ Release for {package_name} completed successfully[/green]")
            else:
                console.print(f"[red]✗ Release for {package_name} failed[/red]")
                all_successful = False
        except Exception as e:
            console.print(f"[red]✗ Error monitoring release for {package_name}: {e}[/red]")
            all_successful = False

    if not all_successful:
        console.print("[red]✗ Some releases failed[/red]")
        raise typer.Exit(1)
    else:
        console.print(f"[green]✓ All {len(releases_created)} releases completed successfully[/green]")


def process_batch_rebuild(package_names: List[str]) -> None:
    """Process a batch of packages that need rebuilding.

    This function:
    1. Marks each package for rebuild by adding a comment to its argfile.conf
    2. Commits and pushes the changes
    3. Waits for GitHub commit checks to complete
    4. Verifies all checks passed

    Args:
        package_names: List of package names to mark for rebuild
    """
    if not package_names:
        console.print("[yellow]No packages to rebuild[/yellow]")
        return

    console.print(f"[blue]Processing {len(package_names)} packages for rebuild: {', '.join(package_names)}[/blue]")

    # Step 1: Mark each package for rebuild
    console.print("[blue]Marking packages for rebuild...[/blue]")
    for package_name in package_names:
        try:
            mark_package_for_rebuild(package_name)
            console.print(f"[green]✓ Marked {package_name} for rebuild[/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed to mark {package_name} for rebuild: {e}[/red]")
            raise

    # Step 2: Commit and push changes
    console.print("[blue]Committing and pushing changes...[/blue]")
    try:
        commit_sha = commit_and_push_changes(package_names)
        console.print(f"[green]✓ Successfully pushed commit {commit_sha[:8]}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to commit and push changes: {e}[/red]")
        raise

    # Step 3: Wait for commit checks to complete
    console.print("[blue]Monitoring commit checks...[/blue]")
    try:
        success = wait_for_commit_checks(commit_sha)
        if success:
            console.print(f"[green]✓ All checks passed for rebuild batch[/green]")
        else:
            console.print(f"[red]✗ Some checks failed for rebuild batch[/red]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error monitoring commit checks: {e}[/red]")
        raise


def fix_issues(
    issues_file: str = typer.Argument(
        ...,
        help="JSON file containing issues from calunga find-issues"
    ),
    batch_rebuild: int = typer.Option(
        20,
        "--batch-rebuild",
        "-b",
        help="Number of 'needs_rebuild' issues to process at once (default: 20)"
    ),
) -> None:
    """Fix issues identified by calunga find-issues.

    This command processes the JSON output from calunga find-issues and attempts
    to fix the identified issues. Currently supports:

    - needs_rebuild: Processes packages in batches (placeholder implementation)
    - Other issue types: Currently ignored with warnings

    The command will continue processing all issues from the report.
    """
    issues_path = Path(issues_file)

    if not issues_path.exists():
        console.print(f"[red]Error: Issues file not found at {issues_path}[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold blue]Calunga Issue Fixer[/bold blue]\n"
        f"Issues file: {issues_path}\n"
        f"Batch rebuild size: {batch_rebuild}",
        title="🔧 Fix Issues",
        border_style="blue",
    ))

    # Load and parse the issues file
    try:
        with open(issues_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error: Invalid JSON in issues file: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error reading issues file: {e}[/red]")
        raise typer.Exit(1)

    # Extract issues from the data
    issues = data.get("issues", None)
    if issues is None:
        console.print("[green]No issues found in the report. Nothing to fix![/green]")
        return
    if not issues:
        console.print("[green]No issues found in the report. Nothing to fix![/green]")
        return

    console.print(f"[blue]Found {len(issues)} issues to process[/blue]")

    # Group issues by type
    issues_by_type: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        issue_type = issue.get("issue_type", "unknown")
        if issue_type not in issues_by_type:
            issues_by_type[issue_type] = []
        issues_by_type[issue_type].append(issue)

    # Process each issue type
    for issue_type, type_issues in issues_by_type.items():
        console.print(f"\n[bold]Processing {len(type_issues)} {issue_type} issues:[/bold]")

        if issue_type == "needs_rebuild":
            # Process rebuild issues in batches
            package_names = [issue["package_name"] for issue in type_issues]

            for i in range(0, len(package_names), batch_rebuild):
                batch = package_names[i:i + batch_rebuild]
                console.print(f"[blue]Processing batch {i // batch_rebuild + 1} ({len(batch)} packages)[/blue]")
                process_batch_rebuild(batch)

        elif issue_type == "needs_release":
            # Process release issues in batches
            for i in range(0, len(type_issues), batch_rebuild):
                batch = type_issues[i:i + batch_rebuild]
                console.print(f"[blue]Processing batch {i // batch_rebuild + 1} ({len(batch)} packages)[/blue]")
                process_batch_release(batch)

        elif issue_type == "unknown":
            console.print(f"[yellow]Warning: 'unknown' issue type not yet implemented.[/yellow]")
            console.print(f"[yellow]Would process {len(type_issues)} unknown issues[/yellow]")

        else:
            console.print(f"[yellow]Warning: Unknown issue type '{issue_type}' not yet implemented.[/yellow]")
            console.print(f"[yellow]Would process {len(type_issues)} {issue_type} issues[/yellow]")

    console.print(Panel(
        f"[bold green]✅ Finished processing all {len(issues)} issues[/bold green]",
        title="Complete",
        border_style="green",
    ))