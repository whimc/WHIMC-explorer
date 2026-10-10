"""Read-only Python runtime report; run in the selected cPanel app virtualenv."""
import importlib.util
import json
import platform
import ssl
import sqlite3
import sys


def report():
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "operating_system": platform.system(),
        "virtualenv_active": sys.prefix != sys.base_prefix,
        "openssl_version": ssl.OPENSSL_VERSION,
        "sqlite_version": sqlite3.sqlite_version,
        "package_presence": {
            name: importlib.util.find_spec(name) is not None
            for name in ("django", "pip", "MySQLdb")
        },
        "not_checked": [
            "Account quotas or hosting approval",
            "Runtime security-support lifecycle",
            "Passenger routing and Shibboleth authorization",
            "Database/network connectivity",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
