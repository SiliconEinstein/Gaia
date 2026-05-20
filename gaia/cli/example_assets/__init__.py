"""Static assets bundled with ``gaia example <flavor>``.

Each subdirectory (``galileo``, ``mendel``, ...) holds a single
``walkthrough.sh`` — a runnable bash script that drives the full cli
authoring sequence for that example package. The cli verb at
:mod:`gaia.cli.commands.example` reads these scripts via
:func:`importlib.resources.files`, applies the ``--target NAME``
placeholder substitution, and either prints the result to stdout or
writes it to a user-chosen file.

Adding a new example: create ``gaia/cli/example_assets/<flavor>/
walkthrough.sh`` with a placeholder of the form
``./<flavor>-cli-mirror-gaia``, wire a new subverb under
:mod:`gaia.cli.commands.example`, and register it in
:mod:`gaia.cli.commands.example.__init__`.
"""
