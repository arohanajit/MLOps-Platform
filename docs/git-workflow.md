# Git Workflow & Branching Strategy

This document outlines the Git workflow and branching strategy for the MLOps platform project.

## Branching Strategy

We follow a simplified GitFlow branching model with the following branches:

### Main Branches

- **`main`**: The production branch, containing the code currently deployed to production.
- **`develop`**: The development branch, containing the latest delivered development changes for the next release.

### Supporting Branches

- **`feature/*`**: Feature branches are used to develop new features for the upcoming or a future release.
- **`bugfix/*`**: Bugfix branches are used to fix bugs in the upcoming release.
- **`hotfix/*`**: Hotfix branches are used to quickly patch production releases.
- **`release/*`**: Release branches support preparation of a new production release.

## Branch Naming Conventions

- Feature branches: `feature/short-description` or `feature/JIRA-123-short-description`
- Bugfix branches: `bugfix/short-description` or `bugfix/JIRA-123-short-description`
- Hotfix branches: `hotfix/short-description` or `hotfix/JIRA-123-short-description`
- Release branches: `release/v1.2.3`

## Workflow

### Feature Development

1. Create a feature branch from `develop`:
   ```bash
   git checkout develop
   git pull
   git checkout -b feature/my-feature
   ```

2. Work on your feature, committing changes as needed.

3. Push your feature branch to the remote repository:
   ```bash
   git push -u origin feature/my-feature
   ```

4. When the feature is complete, create a pull request to `develop`.

5. After code review and CI checks pass, merge the feature into `develop`.

### Release Process

1. Create a release branch from `develop`:
   ```bash
   git checkout develop
   git pull
   git checkout -b release/v1.2.3
   ```

2. Make any final adjustments, version bumps, or documentation updates.

3. Create a pull request to merge the release branch into `main`.

4. After approval, merge the release branch into `main`.

5. Tag the release in `main`:
   ```bash
   git checkout main
   git pull
   git tag -a v1.2.3 -m "Release v1.2.3"
   git push origin v1.2.3
   ```

6. Merge `main` back into `develop` to ensure any release-specific changes are included:
   ```bash
   git checkout develop
   git merge main
   git push
   ```

### Hotfix Process

1. Create a hotfix branch from `main`:
   ```bash
   git checkout main
   git pull
   git checkout -b hotfix/critical-bug
   ```

2. Fix the issue and commit your changes.

3. Create pull requests to merge the hotfix into both `main` and `develop`.

4. After approval, merge into `main` and tag a new release:
   ```bash
   git checkout main
   git pull
   git tag -a v1.2.4 -m "Hotfix v1.2.4"
   git push origin v1.2.4
   ```

5. Merge into `develop` as well.

## Pull Request Guidelines

- Provide a clear, descriptive title and description for your PR
- Reference related issues or tickets
- Keep PRs focused on a single feature or bugfix
- Ensure all CI checks pass before requesting review
- Request review from at least one other team member
- Address review comments promptly

## Commit Message Guidelines

We follow conventional commits for clear and structured commit messages:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types include:
- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, etc.)
- **refactor**: Code refactoring
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **chore**: Maintenance tasks

Examples:
```
feat(model-serving): add caching for prediction requests
fix(data-processing): resolve null value handling in Spark job
docs(readme): update installation instructions
``` 