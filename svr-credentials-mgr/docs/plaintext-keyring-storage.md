# Plaintext Keyring Storage

## What it is

The bundled plaintext backend is a Python keyring plugin implemented in
`plaintext-keyring/src/opamp_plaintext_keyring/backend.py`.

It stores keyring secrets in a human-readable JSON file. It is intentionally unencrypted and is
appropriate only for controlled development or tightly managed administrative environments.

## File location behavior

The plaintext backend chooses its file path in this order:

1. explicit constructor `file_path`
2. `SVR_CREDENTIALS_PLAINTEXT_PATH`
3. config value `opamp.svr_credentials_manager.storage.plaintext_path`
4. default user path:
   - `~/.opamp/credentials-plaintext.json`

The batch launcher overrides this with:

- `data/credentials.json`

## On-disk format

The backend stores service names, then account names, then secret strings. For this component
the keyring service name is:

- `opamp-server-connection-settings`

Accounts used by the credentials manager include:

- `__connection_names__`
  - JSON array of saved connection names
- `connection:<name>`
  - JSON string for the stored connection definition

A representative plaintext file looks like:

```json
{
  "opamp-server-connection-settings": {
    "__connection_names__": "[\"production\",\"shared\"]",
    "connection:shared": "{\"opamp\":{\"destination_endpoint\":\"https://example.test\",\"headers\":{}}}"
  }
}
```

## Security characteristics

The plaintext backend:

- does not encrypt credential values
- writes atomically through a temporary file
- requests owner-only permissions with file mode `0600` on write
- depends on host filesystem ACLs and operator access controls for real protection

## Operational guidance

Use plaintext storage only when all of the following are acceptable:

- the host is already tightly access-controlled
- local disk access is trusted
- backups and log shipping are handled carefully
- human-readable secrets on disk are an acceptable tradeoff for simple operations

Use `cryptfile` instead when stored connection definitions must not remain readable at rest.
