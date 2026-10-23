# Security notes

LocalPilot is a supervised, single-user private MVP, not a security-audited multi-tenant hosting service. Keep its ports on loopback and its app behind the intended private network. The Windows user/backend and their keys are trusted approval authorities. Approved Linux code has the pilot account's own file/network access; desktop ownership is a coordination gate rather than a universal guest lock.

Do not publish `.local`, SSH keys, passwords/hashes, browser sessions, task databases, screenshots, installation media, or backups. Backup files are access-restricted locally but not separately encrypted. A local-only backup does not protect against drive loss. Never disable SSH host verification to recover a connection.

Routine auto-approval is off by default and permits only the documented guest-enforced grammar. Scripts, installations, destructive/compound commands, and desktop inputs retain review. Browser/web/file content is untrusted; prompt injection is not comprehensively solved. Browser security upgrades need operator maintenance.

If a credential is ever published, removing the file alone is insufficient: revoke/rotate it and assess repository history and copies. Do not place credentials or private logs in a public issue. No dedicated security-reporting address has been configured; arrange a private reporting route with the repository owner before sharing sensitive details.
