# Security Notice: Rotating Exposed Secrets

If you have ever committed sensitive credentials (API keys, passwords, etc.) to a public repository, you should:

1. **Revoke and rotate all exposed credentials immediately.**
   - For database credentials, change the password in your database and update your .env file.
   - For API keys (e.g., Google API Key), generate a new key in the provider's console and update your .env file.
2. **Purge secrets from git history** (optional but recommended for public repos):
   - Use tools like `git filter-branch`, `bfg-repo-cleaner`, or `git filter-repo` to remove secrets from commit history.
   - See: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
3. **Never commit .env or config files with secrets.**
   - Always use a .gitignore to exclude them.
4. **Notify affected parties** if any credentials were exposed.

**Summary:**
- All secrets in this project are now loaded from environment variables.
- The .env file is excluded from version control.
- Example .env provided for safe sharing.

Stay safe!
