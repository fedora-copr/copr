from copr_keygen import app

gpg_cmd = [
    app.config['GPG_BINARY'],
    '--homedir', app.config['GNUPG_HOMEDIR'],
    '--no-auto-check-trustdb'
]
