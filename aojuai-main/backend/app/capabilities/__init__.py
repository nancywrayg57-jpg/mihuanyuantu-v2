"""Self-contained, deployable business capabilities.

Each direct child package exposes one ``CAPABILITY`` declaration.  Discovery is
centralised in :mod:`app.core.capability_registry`; adding a module never requires
editing the API router or the feature catalog by hand.
"""

