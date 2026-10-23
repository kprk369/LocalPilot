# Contributing

LocalPilot currently targets Windows 11/Hyper-V, one Ubuntu VM, iPhone/iOS, and one local Ollama 27B model. See docs/setup-and-operation.md before attempting provisioning. A clean-machine end-to-end installer has not yet been validated.

For unit tests, create a Python 3.12 virtual environment and install requirements-dev.txt:

    python -m venv .venv
    python -m pip install -r requirements-dev.txt
    python -m pytest -q

Activate the environment or use its interpreter explicitly. Normal tests use isolated temporary files/fake services; live integration checks are skipped by default. Do not enable LOCALPILOT_INTEGRATION, LOCALPILOT_PACKAGE_INTEGRATION, or LOCALPILOT_GUI_INTEGRATION against someone else's installation. Live tests require private provisioning/configuration and write unique QA files. Desktop tests must not run while a person is using the shared session.

Keep `.local`, VM disks/media, credentials, database/history, logs, backups, screenshots, and personal network details out of commits and issue reports. Before publication, run:

    python -m scripts.check_publication

The check reports filenames/reasons, not secret values. It scans publication candidates and known local secrets, but is not a substitute for human review or a security audit. Do not weaken pinned identity, approval, origin, ownership, or workspace checks to make tests pass. Document validation limits and distinguish a fake/unit check from a real VM or physical iPhone check.

A project license has not yet been selected. Do not assume permission terms that are absent from the repository.
