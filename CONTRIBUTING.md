# Contributing

Thanks for your interest in improving this practice.

## Reporting issues

Open an issue with a reproducible case, the region and runtime you used, and the
output of the verification commands. Do not paste access keys, project IDs or
other private identifiers.

## Pull requests

1. Fork the repository and work from the default branch.
2. Keep changes focused; one behaviour change per pull request.
3. Run the local checks before submitting:

   ```bash
   cd infra
   terraform fmt -check
   terraform validate
   cd ..
   bash scripts/package-function.sh
   python scripts/local-e2e/test_e2e.py
   ```

4. Update both `README.md` and `README.cn.md` when behaviour or verification
   steps change, and keep the architecture diagrams in sync with
   `docs/architecture.md`.

## License

By contributing you agree that your contribution is licensed under the
MIT No Attribution license found in `LICENSE`.
