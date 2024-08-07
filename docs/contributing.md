# Contributing

Thank you for considering contributing to this project! We appreciate your efforts to improve and expand our work. Here are the steps and guidelines for contributing.

## Developing

- This project follows the [Conventional Commits](https://www.conventionalcommits.org/) standard to automate [Semantic Versioning](https://semver.org/) and [Keep A Changelog](https://keepachangelog.com/) with [Commitizen](https://github.com/commitizen-tools/commitizen).
- Run `poetry add {package}` from within the development environment to install a run time dependency and add it to `pyproject.toml` and `poetry.lock`. Add `--group test` or `--group dev` to install a CI or development dependency, respectively.
- Run `poetry update` from within the development environment to upgrade all dependencies to the latest versions allowed by `pyproject.toml`.
- Run `cz bump` to bump the app's version, update the `CHANGELOG.md`, and create a git tag.

## Contributing Steps

1. Create a feature branch:

    ```sh
    git checkout -b feature/my-new-feature
    ```

2. If you updated `pyproject.toml` manually, update the lock file:

    ```sh
    poetry lock
    ```

3. Stage your changes:

    ```sh
    git add <file>
    ```

4. Install dependencies:

    ```sh
    poetry install --with dev
    ```

5. Install pre-commit hooks:

    ```sh
    poetry run pre-commit install
    ```

6. Run (and rerun) pre-commit hooks command, fixing issues until all tests pass:

    ```sh
    poetry run pre-commit run --all-files --verbose
    ```

    - This will automatically fix issues where possible, but some issues may require manual fixing.

7. Commit using Commitizen:

    ```sh
    poetry run cz c
    ```

    - Follow the prompts to create a conventional commit.

8. Push to GitHub:

    ```sh
    git push origin feature/my-new-feature
    ```

9. Go to GitHub and create a pull request from your recent feature branch.
    - Add a reviewer.

Thank you for your contribution!
