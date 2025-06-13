#!/usr/bin/env python3
"""
Setup script for Claude Conductor
"""

from setuptools import setup, find_packages
import os
import re

# Read version from conductor/__init__.py
def get_version():
    with open(os.path.join("conductor", "__init__.py"), "r") as f:
        content = f.read()
        match = re.search(r'__version__ = ["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
    return "0.1.0"

# Read long description from README.md
def get_long_description():
    with open("README.md", "r", encoding="utf-8") as f:
        return f.read()

# Read requirements from requirements.txt
def get_requirements():
    with open("requirements.txt", "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

# Read optional requirements
def get_optional_requirements():
    extras = {}
    
    # Development dependencies
    dev_deps = [
        "pytest>=7.4.0",
        "pytest-asyncio>=0.21.0",
        "pytest-timeout>=2.1.0",
        "pytest-mock>=3.10.0",
        "pytest-cov>=4.0.0",
        "pytest-xdist>=3.2.0",
        "black>=23.0.0",
        "flake8>=6.0.0",
        "mypy>=1.0.0",
        "bandit>=1.7.0",
        "safety>=2.3.0",
        "pre-commit>=3.0.0"
    ]
    
    # Web UI dependencies
    web_deps = [
        "fastapi>=0.100.0",
        "uvicorn>=0.22.0",
        "jinja2>=3.1.0",
        "websockets>=11.0.0",
        "aiofiles>=23.0.0"
    ]
    
    # Database/Redis dependencies
    db_deps = [
        "redis>=4.6.0",
        "sqlalchemy>=2.0.0",
        "alembic>=1.11.0",
        "asyncpg>=0.28.0"
    ]
    
    # Monitoring dependencies
    monitoring_deps = [
        "prometheus-client>=0.17.0",
        "opentelemetry-api>=1.18.0",
        "opentelemetry-sdk>=1.18.0",
        "structlog>=23.1.0"
    ]
    
    # Kubernetes dependencies
    k8s_deps = [
        "kubernetes>=27.0.0",
        "pyyaml>=6.0"
    ]
    
    extras["dev"] = dev_deps
    extras["web"] = web_deps
    extras["db"] = db_deps
    extras["monitoring"] = monitoring_deps
    extras["k8s"] = k8s_deps
    extras["all"] = dev_deps + web_deps + db_deps + monitoring_deps + k8s_deps
    
    return extras

setup(
    name="claude-conductor",
    version=get_version(),
    author="Claude Conductor Team",
    author_email="noreply@claude-conductor.local",
    description="Multi-agent orchestration system for Claude Code instances",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/ootakazuhiko/claude-conductor",
    project_urls={
        "Bug Reports": "https://github.com/ootakazuhiko/claude-conductor/issues",
        "Source": "https://github.com/ootakazuhiko/claude-conductor",
        "Documentation": "https://github.com/ootakazuhiko/claude-conductor/blob/main/docs/",
    },
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Distributed Computing",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities",
    ],
    python_requires=">=3.10",
    install_requires=get_requirements(),
    extras_require=get_optional_requirements(),
    entry_points={
        "console_scripts": [
            "claude-conductor=conductor.orchestrator:main",
            "conductor=conductor.orchestrator:main",
            "claude-orchestrator=conductor.orchestrator:main",
        ],
    },
    include_package_data=True,
    package_data={
        "conductor": ["py.typed"],
    },
    zip_safe=False,
    keywords=[
        "claude",
        "orchestration",
        "multi-agent",
        "automation",
        "containerization",
        "distributed-computing",
        "task-management",
        "parallel-processing"
    ],
    platforms=["any"],
    license="MIT",
    test_suite="tests",
    cmdclass={},
    options={
        "bdist_wheel": {
            "universal": False,
        },
        "egg_info": {
            "tag_build": "",
            "tag_date": False,
        },
    },
)