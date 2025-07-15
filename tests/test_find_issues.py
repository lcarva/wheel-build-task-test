"""Tests for the find-issues command."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests
from typer.testing import CliRunner
import typer

from calunga.commands.find_issues import (
    package_version,
    index_version,
    latest_built_commit_id,
    latest_commit_id,
    find_snapshot_for_commit_id,
    analyze_package,
    find_packages,
    find_issues,
    PYPI_INDEX_URL,
)
from calunga.cli import app

runner = CliRunner()


class TestPackageVersion:
    """Test package_version function."""

    def test_package_version_found(self, tmp_path):
        """Test extracting package version from requirements.txt."""
        pkg_dir = tmp_path / "test-package"
        pkg_dir.mkdir()

        req_file = pkg_dir / "requirements.txt"
        req_file.write_text("test-package==1.2.3\nother-package==4.5.6\n")

        result = package_version(pkg_dir)
        assert result == "1.2.3"

    def test_package_version_not_found(self, tmp_path):
        """Test when package version is not in requirements.txt."""
        pkg_dir = tmp_path / "test-package"
        pkg_dir.mkdir()

        req_file = pkg_dir / "requirements.txt"
        req_file.write_text("other-package==4.5.6\n")

        result = package_version(pkg_dir)
        assert result is None

    def test_requirements_file_not_exists(self, tmp_path):
        """Test when requirements.txt doesn't exist."""
        pkg_dir = tmp_path / "test-package"
        pkg_dir.mkdir()

        result = package_version(pkg_dir)
        assert result is None

    def test_case_insensitive_match(self, tmp_path):
        """Test case insensitive package name matching."""
        pkg_dir = tmp_path / "Test-Package"
        pkg_dir.mkdir()

        req_file = pkg_dir / "requirements.txt"
        req_file.write_text("Test-Package==1.2.3\n")

        result = package_version(pkg_dir)
        assert result == "1.2.3"

    def test_package_version_with_line_continuation(self, tmp_path):
        """Test extracting package version with line continuation."""
        pkg_dir = tmp_path / "test-package"
        pkg_dir.mkdir()

        req_file = pkg_dir / "requirements.txt"
        req_file.write_text("test-package==1.2.3 \\\nother-package==4.5.6\n")

        result = package_version(pkg_dir)
        assert result == "1.2.3"


class TestIndexVersion:
    """Test index_version function."""

    @patch("calunga.commands.find_issues.requests.get")
    def test_index_version_found(self, mock_get):
        """Test extracting version from index HTML."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <body>
                <a href="test-package-1.2.3.tar.gz">test-package-1.2.3.tar.gz</a>
                <a href="test-package-1.2.4.tar.gz">test-package-1.2.4.tar.gz</a>
            </body>
        </html>
        """
        mock_get.return_value = mock_response

        result = index_version("test-package")
        assert result == "1.2.4"

    @patch("calunga.commands.find_issues.requests.get")
    def test_index_version_404(self, mock_get):
        """Test when package is not found in index."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = index_version("test-package")
        assert result == "MISSING"

    @patch("calunga.commands.find_issues.requests.get")
    def test_index_version_no_tar_gz_files(self, mock_get):
        """Test when no .tar.gz files are found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><a href='other-file.txt'>other-file.txt</a></body></html>"
        mock_get.return_value = mock_response

        result = index_version("test-package")
        assert result is None

    @patch("calunga.commands.find_issues.requests.get")
    def test_index_version_request_exception(self, mock_get):
        """Test when request fails."""
        mock_get.side_effect = requests.RequestException("Network error")

        result = index_version("test-package")
        assert result is None


class TestLatestBuiltCommitId:
    """Test latest_built_commit_id function."""

    @patch("calunga.commands.find_issues.subprocess.run")
    def test_latest_built_commit_id_success(self, mock_run):
        """Test successful extraction of commit ID."""
        mock_result = Mock()
        mock_result.stdout = """
        apiVersion: appstudio.redhat.com/v1alpha1
        kind: Component
        status:
          lastBuiltCommit: abc123def456
        """
        mock_run.return_value = mock_result

        result = latest_built_commit_id("test-package")
        assert result == "abc123def456"

    @patch("calunga.commands.find_issues.subprocess.run")
    def test_latest_built_commit_id_no_status(self, mock_run):
        """Test when status is missing."""
        mock_result = Mock()
        mock_result.stdout = """
        apiVersion: appstudio.redhat.com/v1alpha1
        kind: Component
        """
        mock_run.return_value = mock_result

        result = latest_built_commit_id("test-package")
        assert result is None

    @patch("calunga.commands.find_issues.subprocess.run")
    def test_latest_built_commit_id_subprocess_error(self, mock_run):
        """Test when subprocess fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "oc")

        result = latest_built_commit_id("test-package")
        assert result is None


class TestLatestCommitId:
    """Test latest_commit_id function."""

    @patch("calunga.commands.find_issues.subprocess.run")
    def test_latest_commit_id_success(self, mock_run):
        """Test successful extraction of commit ID."""
        mock_result = Mock()
        mock_result.stdout = "abc123def456\n"
        mock_run.return_value = mock_result

        pkg_dir = Path("/tmp/test-package")
        result = latest_commit_id(pkg_dir)
        assert result == "abc123def456"

    @patch("calunga.commands.find_issues.subprocess.run")
    def test_latest_commit_id_subprocess_error(self, mock_run):
        """Test when subprocess fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        pkg_dir = Path("/tmp/test-package")
        result = latest_commit_id(pkg_dir)
        assert result is None


class TestFindSnapshotForCommitId:
    """Test find_snapshot_for_commit_id function."""

    @patch("calunga.commands.find_issues.subprocess.run")
    def test_find_snapshot_success(self, mock_run):
        """Test successful snapshot finding."""
        mock_result = Mock()
        mock_result.stdout = "test-package-abc123def456"
        mock_run.return_value = mock_result

        result = find_snapshot_for_commit_id("test-package", "abc123def456")
        assert result == "test-package-abc123def456"

    @patch("calunga.commands.find_issues.subprocess.run")
    def test_find_snapshot_empty_result(self, mock_run):
        """Test when no snapshot is found."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        result = find_snapshot_for_commit_id("test-package", "abc123def456")
        assert result is None

    @patch("calunga.commands.find_issues.subprocess.run")
    def test_find_snapshot_subprocess_error(self, mock_run):
        """Test when subprocess fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "oc")

        result = find_snapshot_for_commit_id("test-package", "abc123def456")
        assert result is None


class TestAnalyzePackage:
    """Test analyze_package function."""

    @patch("calunga.commands.find_issues.package_version")
    @patch("calunga.commands.find_issues.index_version")
    @patch("calunga.commands.find_issues.latest_built_commit_id")
    @patch("calunga.commands.find_issues.latest_commit_id")
    @patch("calunga.commands.find_issues.find_snapshot_for_commit_id")
    def test_analyze_package_no_issue(self, mock_find_snapshot, mock_latest_commit,
                                     mock_latest_built, mock_index_version, mock_package_version):
        """Test when no issues are found."""
        pkg_dir = Path("/tmp/test-package")

        mock_package_version.return_value = "1.2.3"
        mock_index_version.return_value = "1.2.3"
        mock_latest_built.return_value = "abc123"
        mock_latest_commit.return_value = "abc123"
        mock_find_snapshot.return_value = None

        result = analyze_package(pkg_dir)

        assert result["package_name"] == "test-package"
        assert result["git_version"] == "1.2.3"
        assert result["index_version"] == "1.2.3"
        assert result["issue_type"] == "no_issue"
        assert result["action_needed"] == "none"

    @patch("calunga.commands.find_issues.package_version")
    @patch("calunga.commands.find_issues.index_version")
    @patch("calunga.commands.find_issues.latest_built_commit_id")
    @patch("calunga.commands.find_issues.latest_commit_id")
    @patch("calunga.commands.find_issues.find_snapshot_for_commit_id")
    def test_analyze_package_needs_rebuild(self, mock_find_snapshot, mock_latest_commit,
                                          mock_latest_built, mock_index_version, mock_package_version):
        """Test when package needs rebuild."""
        pkg_dir = Path("/tmp/test-package")

        mock_package_version.return_value = "1.2.4"
        mock_index_version.return_value = "1.2.3"
        mock_latest_built.return_value = "abc123"
        mock_latest_commit.return_value = "def456"
        mock_find_snapshot.return_value = None

        result = analyze_package(pkg_dir)

        assert result["issue_type"] == "needs_rebuild"
        assert result["action_needed"] == "rebuild"
        assert "Commit mismatch" in result["issue_description"]

    @patch("calunga.commands.find_issues.package_version")
    @patch("calunga.commands.find_issues.index_version")
    @patch("calunga.commands.find_issues.latest_built_commit_id")
    @patch("calunga.commands.find_issues.latest_commit_id")
    @patch("calunga.commands.find_issues.find_snapshot_for_commit_id")
    def test_analyze_package_needs_release(self, mock_find_snapshot, mock_latest_commit,
                                          mock_latest_built, mock_index_version, mock_package_version):
        """Test when package needs release."""
        pkg_dir = Path("/tmp/test-package")

        mock_package_version.return_value = "1.2.4"
        mock_index_version.return_value = "1.2.3"
        mock_latest_built.return_value = "abc123"
        mock_latest_commit.return_value = "abc123"
        mock_find_snapshot.return_value = "test-package-abc123"

        result = analyze_package(pkg_dir)

        assert result["issue_type"] == "needs_release"
        assert result["action_needed"] == "release"
        assert "Build exists but not released" in result["issue_description"]


class TestFindPackages:
    """Test find_packages function."""

    def test_find_packages_success(self, tmp_path):
        """Test finding package directories."""
        packages_dir = tmp_path / "packages"
        packages_dir.mkdir()

        # Create some package directories
        (packages_dir / "package1").mkdir()
        (packages_dir / "package2").mkdir()
        (packages_dir / "not-a-package.txt").write_text("not a directory")

        result = find_packages(packages_dir)

        assert len(result) == 2
        assert any("package1" in str(p) for p in result)
        assert any("package2" in str(p) for p in result)

    def test_find_packages_directory_not_exists(self, tmp_path):
        """Test when packages directory doesn't exist."""
        packages_dir = tmp_path / "nonexistent"

        with pytest.raises(typer.BadParameter):
            find_packages(packages_dir)


class TestFindIssuesCLI:
    """Test the find-issues CLI command."""

    @patch("calunga.commands.find_issues.find_packages")
    @patch("calunga.commands.find_issues.analyze_package")
    def test_find_issues_command_success(self, mock_analyze, mock_find_packages, tmp_path):
        """Test successful execution of find-issues command."""
        # Setup mock data
        packages_dir = tmp_path / "packages"
        packages_dir.mkdir()

        mock_find_packages.return_value = [Path("/tmp/packages/pkg1"), Path("/tmp/packages/pkg2")]

        mock_analyze.side_effect = [
            {
                "package_name": "pkg1",
                "git_version": "1.2.3",
                "index_version": "1.2.3",
                "issue_type": "no_issue",
                "action_needed": "none"
            },
            {
                "package_name": "pkg2",
                "git_version": "1.2.4",
                "index_version": "1.2.3",
                "issue_type": "needs_rebuild",
                "action_needed": "rebuild"
            }
        ]

        result = runner.invoke(app, ["find-issues", str(tmp_path)])

        assert result.exit_code == 0
        assert "Found 1 packages with issues" in result.stdout
        assert "needs_rebuild: 1" in result.stdout

    @patch("calunga.commands.find_issues.find_packages")
    def test_find_issues_command_no_packages_dir(self, mock_find_packages, tmp_path):
        """Test when packages directory doesn't exist."""
        result = runner.invoke(app, ["find-issues", str(tmp_path)])

        assert result.exit_code == 1
        assert "packages directory not found" in result.stdout

    @patch("calunga.commands.find_issues.find_packages")
    @patch("calunga.commands.find_issues.analyze_package")
    def test_find_issues_command_output_file(self, mock_analyze, mock_find_packages, tmp_path):
        """Test find-issues command with output file."""
        packages_dir = tmp_path / "packages"
        packages_dir.mkdir()
        output_file = tmp_path / "results.json"

        mock_find_packages.return_value = [Path("/tmp/packages/pkg1")]
        mock_analyze.return_value = {
            "package_name": "pkg1",
            "git_version": "1.2.3",
            "index_version": "1.2.3",
            "issue_type": "no_issue",
            "action_needed": "none"
        }

        result = runner.invoke(app, ["find-issues", str(tmp_path), "--output", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify JSON content
        with open(output_file) as f:
            data = json.load(f)
            assert "summary" in data
            assert "issues" in data
            assert "all_packages" in data

    def test_find_issues_help(self):
        """Test help text for find-issues command."""
        result = runner.invoke(app, ["find-issues", "--help"])
        assert result.exit_code == 0
        assert "Find issues with the Calunga Python index" in result.stdout
        assert "mismatches between git and index" in result.stdout
        assert "JSON format" in result.stdout


class TestFindIssuesIntegration:
    """Integration tests for find-issues command."""

    @patch("calunga.commands.find_issues.analyze_package")
    @patch("calunga.commands.find_issues.find_packages")
    def test_find_issues_integration(self, mock_find_packages, mock_analyze, tmp_path):
        """Integration test with mocked external dependencies."""
        packages_dir = tmp_path / "packages"
        packages_dir.mkdir()
        pkg_dir = packages_dir / "test-package"
        pkg_dir.mkdir()
        req_file = pkg_dir / "requirements.txt"
        req_file.write_text("test-package==1.2.4\n")
        mock_find_packages.return_value = [pkg_dir]
        mock_analyze.return_value = {
            "package_name": "test-package",
            "git_version": "1.2.4",
            "index_version": "1.2.3",
            "built_commit_id": "abc123def456",
            "current_commit_id": "abc123def456",
            "issue_type": "needs_release",
            "issue_description": "Build exists but not released. Snapshot: test-package-abc123def456",
            "action_needed": "release"
        }
        result = runner.invoke(app, ["find-issues", str(tmp_path)])
        assert result.exit_code == 0
        assert "Found 1 packages with issues" in result.stdout
        assert "needs_release: 1" in result.stdout