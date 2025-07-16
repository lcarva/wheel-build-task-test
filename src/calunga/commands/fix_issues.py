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
            console.print(f"[yellow]Warning: 'needs_release' issue type not yet implemented.[/yellow]")
            console.print(f"[yellow]Would process {len(type_issues)} release issues[/yellow]")

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