# AI and package installation

Features and control · 1.3.0.1

1. /ki Install nginx recognizes an installation request and prepares an APT plan. /ki_install nginx requests a plan without AI. Enter a concrete package name on Control. Valid packages from configured APT repositories are allowed; URLs, local .deb files and shell options are not.

2. Review the target package and all dependencies with versions, then confirm separately. Approvals are one-time, bound to identity/message and valid for two minutes. Changed plans are rejected. Already installed targets are not reinstalled.

3. Installation runs in the background on the Linux host. Dependencies may upgrade as planned; package scripts can restart services. Removal and downgrades are not permitted. /ki_install_status shows the last job. Never blindly retry uncertain results; inspect through SSH.

