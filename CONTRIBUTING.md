# Contributing to FastAPI Starter

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/fastapi_starter.git
cd fastapi_starter

# 2. One-click setup
make setup

# 3. Create a feature branch
git checkout -b feature/your-feature-name
```

## Code Style

- **Python**: Follow PEP 8, enforced by `ruff`. Run `ruff check app/ tests/` before committing.
- **TypeScript**: Strict mode, no `any` types.
- **Commits**: Use [Conventional Commits](https://www.conventionalcommits.org/) format:
  - `feat: add new feature`
  - `fix: resolve bug in X`
  - `docs: update README`
  - `refactor: restructure Y`

## Architecture Rules

This project follows strict separation of concerns:

| Layer | Directory | Responsibility |
|-------|-----------|---------------|
| API | `app/api/routers/` | HTTP handling, parameter validation only |
| Service | `app/services/` | All business logic |
| Model | `app/models/` | SQLAlchemy ORM definitions |
| Schema | `app/schemas/` | Pydantic request/response models |
| Worker | `app/worker/` | Celery async tasks |

**Never** put business logic or DB queries in routers. Always call service layer methods.

## Making Changes

1. **Small, focused PRs** — one feature/fix per PR
2. **Add tests** — any new service logic should have corresponding tests in `tests/`
3. **Run tests before pushing**:
   ```bash
   python3 -m pytest tests/ -v
   ruff check app/ tests/
   ```
4. **Database changes** — if you modify `app/models/`, generate a migration:
   ```bash
   alembic revision --autogenerate -m "describe_your_changes"
   alembic upgrade head
   ```
5. **New dependencies** — add to `requirements.txt` (runtime) or `requirements-dev.txt` (dev/test)

## Testing

```bash
# Unit tests
python3 -m pytest tests/ -v

# With coverage
python3 -m pytest --cov=app --cov-report=term-missing

# Lint
ruff check app/ tests/
ruff format --check app/ tests/
```

## Pull Request Process

1. Ensure all tests pass
2. Update documentation if needed (README, CODE_WIKI)
3. Add a clear description of what your PR does
4. Link any related issues

## Reporting Issues

- Use GitHub Issues
- Include steps to reproduce
- Mention your OS, Python version, and Docker version

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
