#!/usr/bin/env python
"""Alembic runner that initializes the Flask app"""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from flask import Flask
from mltf_gateway.server.app import create_app

# Create app context for alembic
app = create_app()

if __name__ == "__main__":
    from alembic import command
    from alembic.config import Config

    # Point to alembic.ini
    alembic_cfg = Config(
        os.path.join(os.path.dirname(__file__), "migrations", "alembic.ini")
    )

    # Set the pythonpath
    alembic_cfg.set_main_option("script_location", "migrations")
    alembic_cfg.set_main_option("prepend_sys_path", "src")

    command.main(alembic_cfg)
