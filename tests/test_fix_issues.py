"""Tests for the fix_issues command."""

import json
import tempfile
from pathlib import Path

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


def test_fix_issues_needs_rebuild():
    """Test fix_issues with needs_rebuild issues."""
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
        assert "Batch rebuild functionality not yet implemented" in result.stdout
        assert "Would rebuild 2 packages: package1, package2" in result.stdout
    finally:
        Path(issues_file).unlink()


def test_fix_issues_needs_rebuild_batch():
    """Test fix_issues with needs_rebuild issues using custom batch size."""
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


def test_fix_issues_mixed_types():
    """Test fix_issues with mixed issue types."""
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