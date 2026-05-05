# Git Workflow

- `main` - production-ready branch, protected, direct pushes forbidden.
- `develop` - integration branch for completed features.
- `feature/*` - one task per branch (required).

## Rules
- Every task must be implemented in a dedicated `feature/*` branch.
- Merge order: `feature/* -> develop -> main`.
- `main` receives changes only via Pull Request from `develop`.

## Naming examples
- `feature/ownership-checks`
- `feature/cqrs-read-sql`
- `feature/domain-events-worker`
