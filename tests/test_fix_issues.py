"""Tests for the fix_issues command."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from calunga.cli import app

runner = CliRunner()


def test_fix_issues_no_issues():
    """Test fix_issues with a JSON file containing no issues."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"issues": []}, f)
        issues_file = f.name

    try:
        result = runner.invoke(app, ["fix-issues", issues_file])
        assert result.exit_code == 0
        assert "No issues found in the report" in result.stdout
    finally:
        Path(issues_file).unlink()


@patch("calunga.commands.fix_issues.mark_package_for_rebuild")
@patch("calunga.commands.fix_issues.commit_and_push_changes")
@patch("calunga.commands.fix_issues.wait_for_commit_checks")
def test_fix_issues_needs_rebuild(mock_wait_checks, mock_commit_push, mock_mark_rebuild):
    """Test fix_issues with needs_rebuild issues."""
    # Mock the functions to avoid actual git/GitHub operations
    mock_mark_rebuild.return_value = None
    mock_commit_push.return_value = "abc123def456"
    mock_wait_checks.return_value = True

    issues_data = {
        "issues": [
            {
                "package_name": "package1",
                "issue_type": "needs_rebuild",
                "issue_description": "Commit mismatch",
                "action_needed": "rebuild"
            },
            {
                "package_name": "package2",
                "issue_type": "needs_rebuild",
                "issue_description": "Commit mismatch",
                "action_needed": "rebuild"
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(issues_data, f)
        issues_file = f.name

    try:
        result = runner.invoke(app, ["fix-issues", issues_file])
        assert result.exit_code == 0
        assert "Processing 2 needs_rebuild issues" in result.stdout
        assert "Processing batch 1 (2 packages)" in result.stdout
        assert "✓ Marked package1 for rebuild" in result.stdout
        assert "✓ Marked package2 for rebuild" in result.stdout
        assert "✓ Successfully pushed commit abc123de" in result.stdout  # Note: truncated in output
        assert "✓ All checks passed for rebuild batch" in result.stdout
    finally:
        Path(issues_file).unlink()


@patch("calunga.commands.fix_issues.mark_package_for_rebuild")
@patch("calunga.commands.fix_issues.commit_and_push_changes")
@patch("calunga.commands.fix_issues.wait_for_commit_checks")
def test_fix_issues_needs_rebuild_batch(mock_wait_checks, mock_commit_push, mock_mark_rebuild):
    """Test fix_issues with needs_rebuild issues using custom batch size."""
    # Mock the functions to avoid actual git/GitHub operations
    mock_mark_rebuild.return_value = None
    mock_commit_push.return_value = "abc123def456"
    mock_wait_checks.return_value = True

    issues_data = {
        "issues": [
            {
                "package_name": f"package{i}",
                "issue_type": "needs_rebuild",
                "issue_description": "Commit mismatch",
                "action_needed": "rebuild"
            }
            for i in range(25)  # More than default batch size of 20
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(issues_data, f)
        issues_file = f.name

    try:
        result = runner.invoke(app, ["fix-issues", issues_file, "--batch-rebuild", "10"])
        assert result.exit_code == 0
        assert "Processing 25 needs_rebuild issues" in result.stdout
        assert "Processing batch 1 (10 packages)" in result.stdout
        assert "Processing batch 2 (10 packages)" in result.stdout
        assert "Processing batch 3 (5 packages)" in result.stdout
    finally:
        Path(issues_file).unlink()


def test_fix_issues_needs_release():
    """Test fix_issues with needs_release issues."""
    issues_data = {
        "issues": [
            {
                "package_name": "package1",
                "issue_type": "needs_release",
                "issue_description": "Build exists but not released",
                "action_needed": "release"
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(issues_data, f)
        issues_file = f.name

    try:
        result = runner.invoke(app, ["fix-issues", issues_file])
        assert result.exit_code == 0
        assert "Processing 1 needs_release issues" in result.stdout
        assert "'needs_release' issue type not yet implemented" in result.stdout
    finally:
        Path(issues_file).unlink()


def test_fix_issues_unknown_type():
    """Test fix_issues with unknown issue type."""
    issues_data = {
        "issues": [
            {
                "package_name": "package1",
                "issue_type": "unknown",
                "issue_description": "Unknown issue",
                "action_needed": "investigate"
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(issues_data, f)
        issues_file = f.name

    try:
        result = runner.invoke(app, ["fix-issues", issues_file])
        assert result.exit_code == 0
        assert "Processing 1 unknown issues" in result.stdout
        assert "'unknown' issue type not yet implemented" in result.stdout
    finally:
        Path(issues_file).unlink()


def test_fix_issues_custom_type():
    """Test fix_issues with a custom issue type."""
    issues_data = {
        "issues": [
            {
                "package_name": "package1",
                "issue_type": "custom_type",
                "issue_description": "Custom issue",
                "action_needed": "custom_action"
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(issues_data, f)
        issues_file = f.name

    try:
        result = runner.invoke(app, ["fix-issues", issues_file])
        assert result.exit_code == 0
        assert "Processing 1 custom_type issues" in result.stdout
        assert "Unknown issue type 'custom_type' not yet implemented" in result.stdout
    finally:
        Path(issues_file).unlink()


@patch("calunga.commands.fix_issues.mark_package_for_rebuild")
@patch("calunga.commands.fix_issues.commit_and_push_changes")
@patch("calunga.commands.fix_issues.wait_for_commit_checks")
def test_fix_issues_mixed_types(mock_wait_checks, mock_commit_push, mock_mark_rebuild):
    """Test fix_issues with mixed issue types."""
    # Mock the functions to avoid actual git/GitHub operations
    mock_mark_rebuild.return_value = None
    mock_commit_push.return_value = "abc123def456"
    mock_wait_checks.return_value = True

    issues_data = {
        "issues": [
            {
                "package_name": "package1",
                "issue_type": "needs_rebuild",
                "issue_description": "Commit mismatch",
                "action_needed": "rebuild"
            },
            {
                "package_name": "package2",
                "issue_type": "needs_release",
                "issue_description": "Build exists but not released",
                "action_needed": "release"
            },
            {
                "package_name": "package3",
                "issue_type": "unknown",
                "issue_description": "Unknown issue",
                "action_needed": "investigate"
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(issues_data, f)
        issues_file = f.name

    try:
        result = runner.invoke(app, ["fix-issues", issues_file])
        assert result.exit_code == 0
        assert "Processing 1 needs_rebuild issues" in result.stdout
        assert "Processing 1 needs_release issues" in result.stdout
        assert "Processing 1 unknown issues" in result.stdout
        assert "Finished processing all 3 issues" in result.stdout
    finally:
        Path(issues_file).unlink()


def test_fix_issues_missing_file():
    """Test fix_issues with a non-existent file."""
    result = runner.invoke(app, ["fix-issues", "nonexistent.json"])
    assert result.exit_code == 1
    assert "Issues file not found" in result.stdout


def test_fix_issues_invalid_json():
    """Test fix_issues with invalid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("invalid json content")
        issues_file = f.name

    try:
        result = runner.invoke(app, ["fix-issues", issues_file])
        assert result.exit_code == 1
        assert "Invalid JSON in issues file" in result.stdout
    finally:
        Path(issues_file).unlink()


def test_fix_issues_missing_issues_key():
    """Test fix_issues with JSON missing the 'issues' key."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"summary": {"total_packages": 0}}, f)
        issues_file = f.name

    try:
        result = runner.invoke(app, ["fix-issues", issues_file])
        assert result.exit_code == 0
        assert "No issues found in the report" in result.stdout
    finally:
        Path(issues_file).unlink()


def test_fix_issues_help():
    """Test fix_issues help text."""
    result = runner.invoke(app, ["fix-issues", "--help"])
    assert result.exit_code == 0
    assert "Fix issues identified by calunga find-issues" in result.stdout
    assert "--batch-rebuild" in result.stdout
    assert "Number of 'needs_rebuild' issues" in result.stdout


# Additional tests for the new functions
def test_mark_package_for_rebuild():
    """Test mark_package_for_rebuild function."""
    from calunga.commands.fix_issues import mark_package_for_rebuild

    # Create a temporary argfile.conf
    with tempfile.TemporaryDirectory() as temp_dir:
        package_dir = Path(temp_dir) / "test_package"
        package_dir.mkdir()
        argfile_path = package_dir / "argfile.conf"

        # Create initial argfile.conf
        with open(argfile_path, "w") as f:
            f.write("PACKAGE_NAME=test_package\n")

        # Mock the Path to point to our temp file
        with patch("calunga.commands.fix_issues.Path") as mock_path:
            mock_path.return_value = argfile_path

            # Test marking for rebuild
            mark_package_for_rebuild("test_package")

            # Verify the file was updated
            with open(argfile_path, "r") as f:
                content = f.read()

            assert "PACKAGE_NAME=test_package" in content
            assert "# Add comment to force rebuild" in content
            assert "2025-" in content  # Should contain current year


def test_mark_package_for_rebuild_missing_file():
    """Test mark_package_for_rebuild with missing argfile.conf."""
    from calunga.commands.fix_issues import mark_package_for_rebuild

    # Mock the Path to return a non-existent file path
    with patch("calunga.commands.fix_issues.Path") as mock_path:
        mock_path.return_value = Path("/nonexistent/path/argfile.conf")

        with pytest.raises(FileNotFoundError):
            mark_package_for_rebuild("nonexistent_package")


@patch("calunga.commands.fix_issues.subprocess.run")
def test_commit_and_push_changes(mock_run):
    """Test commit_and_push_changes function."""
    from calunga.commands.fix_issues import commit_and_push_changes

    # There are two packages, so two git add calls, then commit, rev-parse, push
    mock_add1 = Mock(returncode=0)
    mock_add2 = Mock(returncode=0)
    mock_commit = Mock(returncode=0)
    mock_rev_parse = Mock(returncode=0, stdout="abc123def456\n")
    mock_push = Mock(returncode=0)

    mock_run.side_effect = [mock_add1, mock_add2, mock_commit, mock_rev_parse, mock_push]

    result = commit_and_push_changes(["package1", "package2"])
    assert result == "abc123def456"
    assert mock_run.call_count == 5


@patch("calunga.commands.fix_issues.subprocess.run")
def test_wait_for_commit_checks(mock_run):
    """Test wait_for_commit_checks function."""
    from calunga.commands.fix_issues import wait_for_commit_checks

    # Mock successful API response
    mock_response = {
        "check_runs": [
            {
                "name": "test-check",
                "status": "completed",
                "conclusion": "success"
            }
        ]
    }

    mock_run.return_value = Mock(
        returncode=0,
        stdout=json.dumps(mock_response)
    )

    result = wait_for_commit_checks("abc123def456")
    assert result is True