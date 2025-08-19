"""
ZivoHealth Backend Application Package

Suppress third-party package warnings that are beyond our control.
"""

import warnings

# Suppress pkg_resources deprecation warning from guardrails package
warnings.filterwarnings(
    "ignore", 
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
    module="guardrails.hub.install"
) 