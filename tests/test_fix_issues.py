"""Tests for the fix_issues command."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer
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


@patch("calunga.commands.fix_issues.find_snapshot_for_commit_id")
@patch("calunga.commands.fix_issues.create_release_for_snapshot")
@patch("calunga.commands.fix_issues.wait_for_release_completion")
def test_fix_issues_needs_release(mock_wait_release, mock_create_release, mock_find_snapshot):
    """Test fix_issues with needs_release issues."""
    # Mock the functions to avoid actual oc operations
    mock_find_snapshot.return_value = "package1-abc123"
    mock_create_release.return_value = "managed-xyz789"
    mock_wait_release.return_value = True

    issues_data = {
        "issues": [
            {
                "package_name": "package1",
                "built_commit_id": "abc123",
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
        assert "Processing batch 1 (1 packages)" in result.stdout
        assert "Processing 1 packages for release: package1" in result.stdout
        assert "Finding snapshots and creating releases..." in result.stdout
        assert "Found snapshot package1-abc123 for package1" in result.stdout
        assert "Created release managed-xyz789 for package1" in result.stdout
        assert "Release for package1 completed successfully" in result.stdout
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
@patch("calunga.commands.fix_issues.find_snapshot_for_commit_id")
@patch("calunga.commands.fix_issues.create_release_for_snapshot")
@patch("calunga.commands.fix_issues.wait_for_release_completion")
def test_fix_issues_mixed_types(mock_wait_release, mock_create_release, mock_find_snapshot, mock_wait_checks, mock_commit_push, mock_mark_rebuild):
    """Test fix_issues with mixed issue types."""
    # Mock the functions to avoid actual git/GitHub operations
    mock_mark_rebuild.return_value = None
    mock_commit_push.return_value = "abc123def456"
    mock_wait_checks.return_value = True

    # Mock the release functions
    mock_find_snapshot.return_value = "package2-def456"
    mock_create_release.return_value = "managed-xyz789"
    mock_wait_release.return_value = True

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
                "built_commit_id": "def456",
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


# Tests for the new release-related functions
@patch("calunga.commands.fix_issues.subprocess.run")
def test_find_snapshot_for_commit_id(mock_run):
    """Test find_snapshot_for_commit_id function."""
    from calunga.commands.fix_issues import find_snapshot_for_commit_id

    mock_run.return_value = Mock(
        returncode=0,
        stdout="package1-abc123\n"
    )

    result = find_snapshot_for_commit_id("package1", "abc123")
    assert result == "package1-abc123"

    # Verify the oc command was called correctly
    mock_run.assert_called_once_with(
        [
            "oc", "get", "snapshot",
            "-l", "pac.test.appstudio.openshift.io/sha=abc123,appstudio.openshift.io/component=package1,pac.test.appstudio.openshift.io/event-type=push",
            "-o", "jsonpath={.items[0].metadata.name}"
        ],
        check=True, capture_output=True, text=True
    )


@patch("calunga.commands.fix_issues.subprocess.run")
def test_find_snapshot_for_commit_id_not_found(mock_run):
    """Test find_snapshot_for_commit_id when no snapshot is found."""
    from calunga.commands.fix_issues import find_snapshot_for_commit_id

    mock_run.return_value = Mock(
        returncode=0,
        stdout="\n"  # Empty output
    )

    with pytest.raises(ValueError, match="No snapshot found for package package1 and commit abc123"):
        find_snapshot_for_commit_id("package1", "abc123")


@patch("calunga.commands.fix_issues.subprocess.run")
def test_create_release_for_snapshot(mock_run):
    """Test create_release_for_snapshot function."""
    from calunga.commands.fix_issues import create_release_for_snapshot

    mock_run.return_value = Mock(
        returncode=0,
        stdout="release.appstudio.redhat.com/managed-xyz789 created\n"
    )

    result = create_release_for_snapshot("package1-abc123")
    assert result == "managed-xyz789"

    # Verify the oc command was called correctly
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["oc", "create", "-f", "-"]
    assert call_args[1]["input"] is not None
    assert "package1-abc123" in call_args[1]["input"]


@patch("calunga.commands.fix_issues.subprocess.run")
def test_create_release_for_snapshot_extraction_failure(mock_run):
    """Test create_release_for_snapshot when release name extraction fails."""
    from calunga.commands.fix_issues import create_release_for_snapshot

    mock_run.return_value = Mock(
        returncode=0,
        stdout="unexpected output format\n"
    )

    with pytest.raises(ValueError, match="Could not extract release name from oc create output"):
        create_release_for_snapshot("package1-abc123")


@patch("calunga.commands.fix_issues.subprocess.run")
def test_wait_for_release_completion_success(mock_run):
    """Test wait_for_release_completion with successful completion."""
    from calunga.commands.fix_issues import wait_for_release_completion

    mock_run.return_value = Mock(
        returncode=0,
        stdout="Succeeded\n"
    )

    result = wait_for_release_completion("managed-xyz789")
    assert result is True

    # Verify the oc command was called correctly
    mock_run.assert_called_once_with(
        [
            "oc", "get", "release", "managed-xyz789",
            "-o", "jsonpath={.status.conditions[?(@.type==\"Released\")].reason}"
        ],
        check=True, capture_output=True, text=True
    )


@patch("calunga.commands.fix_issues.subprocess.run")
def test_wait_for_release_completion_failure(mock_run):
    """Test wait_for_release_completion with failed release."""
    from calunga.commands.fix_issues import wait_for_release_completion

    mock_run.return_value = Mock(
        returncode=0,
        stdout="Failed\n"
    )

    result = wait_for_release_completion("managed-xyz789")
    assert result is False


@patch("calunga.commands.fix_issues.subprocess.run")
def test_wait_for_release_completion_timeout(mock_run):
    """Test wait_for_release_completion with timeout."""
    from calunga.commands.fix_issues import wait_for_release_completion

    # Mock empty response to simulate waiting
    mock_run.return_value = Mock(
        returncode=0,
        stdout="\n"
    )

    result = wait_for_release_completion("managed-xyz789", max_wait_minutes=0.1)
    assert result is False


@patch("calunga.commands.fix_issues.find_snapshot_for_commit_id")
@patch("calunga.commands.fix_issues.create_release_for_snapshot")
@patch("calunga.commands.fix_issues.wait_for_release_completion")
def test_process_batch_release_success(mock_wait_release, mock_create_release, mock_find_snapshot):
    """Test process_batch_release with successful releases."""
    from calunga.commands.fix_issues import process_batch_release

    # Mock the functions
    mock_find_snapshot.return_value = "package1-abc123"
    mock_create_release.return_value = "managed-xyz789"
    mock_wait_release.return_value = True

    release_issues = [
        {
            "package_name": "package1",
            "built_commit_id": "abc123"
        }
    ]

    process_batch_release(release_issues)

    # Verify all functions were called correctly
    mock_find_snapshot.assert_called_once_with("package1", "abc123")
    mock_create_release.assert_called_once_with("package1-abc123")
    mock_wait_release.assert_called_once_with("managed-xyz789")


@patch("calunga.commands.fix_issues.find_snapshot_for_commit_id")
@patch("calunga.commands.fix_issues.create_release_for_snapshot")
@patch("calunga.commands.fix_issues.wait_for_release_completion")
def test_process_batch_release_failure(mock_wait_release, mock_create_release, mock_find_snapshot):
    """Test process_batch_release with failed releases."""
    from calunga.commands.fix_issues import process_batch_release

    # Mock the functions
    mock_find_snapshot.return_value = "package1-abc123"
    mock_create_release.return_value = "managed-xyz789"
    mock_wait_release.return_value = False  # Release fails

    release_issues = [
        {
            "package_name": "package1",
            "built_commit_id": "abc123"
        }
    ]

    with pytest.raises(typer.Exit):
        process_batch_release(release_issues)


def test_process_batch_release_empty():
    """Test process_batch_release with empty list."""
    from calunga.commands.fix_issues import process_batch_release

    process_batch_release([])  # Should not raise any exceptions