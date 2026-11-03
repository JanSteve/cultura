"""
Automated Packaging & Submission Kit Test Suite.
Validates LICENSE, pyproject.toml, requirements.txt, .env.example, and README.md.

Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import pytest

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestLicensePackaging:
    """Validate Apache 2.0 LICENSE file requirements."""

    def test_license_file_exists(self) -> None:
        license_path = REPO_ROOT / "LICENSE"
        assert license_path.is_file(), f"LICENSE file missing at {license_path}"
        assert license_path.stat().st_size > 1000, "LICENSE file is unexpectedly small"

    def test_license_contains_apache_2_text(self) -> None:
        content = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
        assert "Apache License" in content
        assert "Version 2.0, January 2004" in content
        assert "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION" in content
        assert "http://www.apache.org/licenses/" in content
        assert "APPENDIX: How to apply the Apache License to your work" in content

    def test_license_exact_copyright_statement(self) -> None:
        content = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
        expected_copyright = "Copyright 2026 R Jan Steve Daniel"
        assert expected_copyright in content, (
            f"Exact copyright notice '{expected_copyright}' not found in LICENSE"
        )


class TestPyprojectTomlPackaging:
    """Validate pyproject.toml PEP 518/621 conformance."""

    @pytest.fixture
    def pyproject_data(self) -> Dict[str, Any]:
        pyproject_path = REPO_ROOT / "pyproject.toml"
        assert pyproject_path.is_file(), f"pyproject.toml missing at {pyproject_path}"

        content = pyproject_path.read_text(encoding="utf-8")
        if tomllib is not None:
            return tomllib.loads(content)

        # Fallback simple parser if tomllib is unavailable
        data: Dict[str, Any] = {"project": {}}
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("name ="):
                data["project"]["name"] = line.split("=", 1)[1].strip().strip('"\'')
            elif line.startswith("version ="):
                data["project"]["version"] = line.split("=", 1)[1].strip().strip('"\'')
        return data

    def test_pyproject_name_and_version(self, pyproject_data: Dict[str, Any]) -> None:
        project = pyproject_data.get("project", {})
        assert project.get("name") == "cultura"
        assert project.get("version") == "0.1.0"

    def test_pyproject_author_metadata(self, pyproject_data: Dict[str, Any]) -> None:
        project = pyproject_data.get("project", {})
        authors = project.get("authors", [])
        author_names = [a.get("name") for a in authors if isinstance(a, dict)]
        assert "R Jan Steve Daniel" in author_names, (
            f"Author 'R Jan Steve Daniel' not found in pyproject.toml authors: {authors}"
        )

    def test_pyproject_license_and_python_requires(self, pyproject_data: Dict[str, Any]) -> None:
        project = pyproject_data.get("project", {})
        license_info = project.get("license", {})
        if isinstance(license_info, dict):
            assert license_info.get("text") == "Apache-2.0"
        else:
            assert "Apache" in str(license_info)

        requires_python = project.get("requires-python", "")
        assert ">=3.10" in requires_python

    def test_pyproject_dependencies(self, pyproject_data: Dict[str, Any]) -> None:
        project = pyproject_data.get("project", {})
        deps = project.get("dependencies", [])
        deps_str = " ".join(deps).lower()

        required_packages = [
            "pydantic",
            "typer",
            "rich",
            "httpx",
            "streamlit",
            "pydeck",
        ]
        for pkg in required_packages:
            assert pkg in deps_str, f"Required dependency '{pkg}' missing from pyproject.toml"

    def test_pyproject_cli_entrypoint(self, pyproject_data: Dict[str, Any]) -> None:
        project = pyproject_data.get("project", {})
        scripts = project.get("scripts", {})
        assert "cultura" in scripts, "CLI script 'cultura' not found in [project.scripts]"
        assert scripts["cultura"] == "cultura.cli.main:app", (
            f"Expected 'cultura.cli.main:app', got '{scripts['cultura']}'"
        )


class TestRequirementsTxtPackaging:
    """Validate requirements.txt dependencies."""

    def test_requirements_file_exists(self) -> None:
        req_path = REPO_ROOT / "requirements.txt"
        assert req_path.is_file(), f"requirements.txt missing at {req_path}"

    def test_requirements_packages_present(self) -> None:
        content = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        required_packages = [
            "pydantic",
            "typer",
            "rich",
            "httpx",
            "streamlit",
            "pydeck",
            "pytest",
            "pytest-asyncio",
        ]
        for pkg in required_packages:
            assert pkg in content, f"Required package '{pkg}' missing from requirements.txt"


class TestEnvExamplePackaging:
    """Validate .env.example configuration template."""

    def test_env_example_exists(self) -> None:
        env_path = REPO_ROOT / ".env.example"
        assert env_path.is_file(), f".env.example missing at {env_path}"

    def test_env_example_contains_qloo_key(self) -> None:
        content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        assert "QLOO_API_KEY" in content, "QLOO_API_KEY missing from .env.example"


class TestReadmePackaging:
    """Validate README.md comprehensive technical pitch & documentation."""

    @pytest.fixture
    def readme_text(self) -> str:
        readme_path = REPO_ROOT / "README.md"
        assert readme_path.is_file(), f"README.md missing at {readme_path}"
        return readme_path.read_text(encoding="utf-8")

    def test_readme_title_and_badges(self, readme_text: str) -> None:
        assert "# CULTURA: Autonomous Cultural Intelligence & Taste Graph Agent" in readme_text
        assert "Python" in readme_text
        assert "Apache" in readme_text
        assert "Qloo" in readme_text
        assert "Doctor SLA" in readme_text or "<100ms" in readme_text

    def test_readme_architecture_diagram(self, readme_text: str) -> None:
        assert "Architecture" in readme_text
        assert "ReAct" in readme_text
        assert "Thought" in readme_text or "THOUGHT" in readme_text
        assert "Action" in readme_text or "ACTION" in readme_text
        assert "Observation" in readme_text or "OBSERVATION" in readme_text
        assert "Synthesis" in readme_text or "SYNTHESIS" in readme_text

    def test_readme_8_hubs_and_7_domains(self, readme_text: str) -> None:
        hubs = [
            "Bangalore",
            "Mumbai",
            "New York",
            "London",
            "Tokyo",
            "Paris",
            "Berlin",
            "San Francisco",
        ]
        domains = [
            "Dining",
            "Music",
            "Arts",
            "Cinema",
            "Nightlife",
            "Literary",
            "Fashion",
        ]
        for hub in hubs:
            assert hub in readme_text, f"Hub '{hub}' missing from README.md"
        for dom in domains:
            assert dom in readme_text, f"Domain '{dom}' missing from README.md"

    def test_readme_cli_guide_and_streamlit(self, readme_text: str) -> None:
        assert "cultura doctor" in readme_text
        assert "cultura plan" in readme_text
        assert "cultura hubs" in readme_text
        assert "cultura search" in readme_text
        assert "streamlit run" in readme_text

    def test_readme_multi_format_exporters(self, readme_text: str) -> None:
        assert "RFC 5545" in readme_text or ".ics" in readme_text
        assert ".geojson" in readme_text or "RFC 7946" in readme_text
        assert ".md" in readme_text
        assert ".json" in readme_text

    def test_readme_hackathon_submission_details(self, readme_text: str) -> None:
        assert "Devpost" in readme_text
        assert "Hackathon" in readme_text

    def test_readme_copyright_attribution(self, readme_text: str) -> None:
        assert "R Jan Steve Daniel" in readme_text
        assert "Copyright 2026 R Jan Steve Daniel" in readme_text


class TestCliImportAndVersion:
    """Validate CLI entrypoint is importable and metadata aligns."""

    def test_cli_app_importable(self) -> None:
        from cultura.cli.main import app
        import typer

        assert isinstance(app, typer.Typer)
        cmd_names = [
            cmd.name or (cmd.callback.__name__ if cmd.callback else None)
            for cmd in app.registered_commands
        ]
        for expected_cmd in ["doctor", "hubs", "search", "plan", "version"]:
            assert expected_cmd in cmd_names, f"Expected CLI command '{expected_cmd}' missing"

    def test_cultura_version(self) -> None:
        import cultura

        assert hasattr(cultura, "__version__")
        assert cultura.__version__ == "0.1.0"
