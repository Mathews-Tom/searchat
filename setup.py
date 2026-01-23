from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8') if (this_directory / "README.md").exists() else ""

setup(
    name="searchat",
    version="0.2.0",
    author="Searchat",
    description="Semantic search for AI coding agents - search Claude Code and Mistral Vibe conversations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "duckdb>=0.10.0",
        "pyarrow>=14.0.0",
        "faiss-cpu>=1.7.4",
        "sentence-transformers>=2.3.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.20.0",
        "rich>=13.0.0",
        "tomli>=2.0.1",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "python-dotenv>=1.0.0",
        "watchdog>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "searchat=searchat.cli:main",
            "searchat-web=searchat.web_api:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)