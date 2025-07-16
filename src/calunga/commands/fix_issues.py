"""Fix issues command for Calunga CLI."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def process_batch_rebuild(package_names: List[str]) -> None:
    """Process a batch of packages that need rebuilding.

    This is a placeholder function that will be implemented later.
    For now, it just emits a warning that it's not yet implemented.
    """
    console.print(f"[yellow]Warning: Batch rebuild functionality not yet implemented.[/yellow]")
    console.print(f"[yellow]Would rebuild {len(package_names)} packages: {', '.join(package_names)}[/yellow]")


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