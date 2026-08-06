from setuptools import setup, find_packages

setup(
    name="ai-context-generator",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "openai>=1.0.0",
        "tomli>=2.0.0; python_version < '3.11'"
    ],
    entry_points={
        "console_scripts": [
            "ai-context-generator=core.cli:main"
        ]
    }
)
