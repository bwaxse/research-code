"""
Helper functions for All of Us workspace setup and configuration.

This module provides utilities for loading workspace environment variables
from the config file created by 00_setup_workspace.ipynb.

USAGE IN VERILY WORKBENCH:
    1. Upload this file to the same directory as your notebooks
       (e.g., /workspace/autoencoder-ehr-project/aou_helpers.py)
    2. Import in your notebooks:

       from aou_helpers import load_aou_env
       env = load_aou_env()
"""

import json
import os
from typing import Dict

CONFIG_PATH = '/home/jupyter/workspace/.aou_config.json'


def load_aou_env() -> Dict[str, str]:
    """
    Load All of Us workspace configuration and set environment variables.

    Reads the workspace config JSON file created by 00_setup_workspace.ipynb
    and updates os.environ with the values. This allows both direct dict access
    and standard os.environ patterns to work.

    Returns:
        dict: Workspace environment variables containing:
            - GOOGLE_CLOUD_PROJECT: Your Google Cloud project ID
            - WORKSPACE_CDR: BigQuery dataset with OMOP CDR data
            - WORKSPACE_BUCKET: Persistent workspace GCS bucket
            - WORKSPACE_TEMP_BUCKET: Temporary workspace GCS bucket

    Raises:
        FileNotFoundError: If config file doesn't exist (run 00_setup_workspace.ipynb first)

    Example:
        >>> from aou_helpers import load_aou_env
        >>> env = load_aou_env()
        >>> # Now use os.environ directly
        >>> WORKSPACE_CDR = os.environ['WORKSPACE_CDR']
    """
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"Config file not found at {CONFIG_PATH}. "
            "Please run _reference/verily/00_setup_workspace.ipynb first."
        )

    with open(CONFIG_PATH) as f:
        env = json.load(f)

    # Update os.environ for compatibility with existing code
    os.environ.update(env)

    return env
