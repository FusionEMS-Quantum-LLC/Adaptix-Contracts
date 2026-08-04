# Contributing to Adaptix Contracts

Thank you for your interest in contributing to the Adaptix Contracts package!

## Getting Started

1. Clone the repository:

   ```bash
   git clone https://github.com/FusionEMS-Quantum-LLC/Adaptix-Contracts.git
   cd Adaptix-Contracts
   ```

2. Install in development mode:

   ```bash
   pip install -e .[dev]
   ```

3. Run the test suite to make sure everything works:

   ```bash
   python -m pytest tests -q --tb=short
   ```

4. Run the validation script:

   ```bash
   python validate_contracts.py
   ```

## Adding New Contracts

When adding new contracts:

1. **Create a new schema file** in `adaptix_contracts/schemas/` following the
   naming convention `{domain}_contracts.py`.
2. **Define your models** using Pydantic v2 `BaseModel` with proper type
   annotations and `Field()` validation.
3. **Export symbols** by adding imports and entries to `adaptix_contracts/schemas/__init__.py`:
   - Add the import block with all symbols from your new module.
   - Add each symbol name to the `__all__` list in the appropriate
     alphabetical/domain section.
4. **Run validation** to verify:

   ```bash
   python validate_contracts.py
   python -m pytest tests -q --tb=short
   ```

5. **Follow existing naming conventions:**
   - Events: `{Domain}{Entity}{Action}Event`
   - Contracts: `{Domain}{Entity}Contract`
   - Enums: descriptive PascalCase names
   - Request/Response: `{Entity}{Action}Request` / `{Entity}{Action}Response`

## Contract Principles

All contributions must follow these principles:

### What belongs here

- Pydantic models for events, requests, and responses
- Enums for canonical statuses and types
- Type annotations for all fields
- Field validation at the schema level
- Shared contract definitions used across domains

### What does NOT belong here

- Business logic or service implementation
- Database models or ORM models
- API routes or HTTP handlers
- Service orchestration or workflow engines
- Infrastructure code (Terraform, Docker, etc.)

## Code Standards

- Python >= 3.11
- Pydantic >= 2.6.0 (v2 patterns only)
- All fields must have type annotations
- Use `Optional[T]` for nullable fields
- Use `Field()` for validation constraints
- Follow existing patterns in nearby contract files

## Pull Request Process

1. Create a feature branch from `main`.
2. Make your changes following the guidelines above.
3. Ensure all tests pass (`python -m pytest tests -q --tb=short`).
4. Ensure validation passes (`python validate_contracts.py`).
5. Update `CHANGELOG.md` with a description of your changes under an
   `[Unreleased]` section.
6. Submit a pull request with a clear description of what you added or changed.

## Versioning

This project follows semantic versioning:

- **Major** - Breaking changes to existing contracts
- **Minor** - New contracts or backward-compatible additions
- **Patch** - Bug fixes, documentation updates

## Questions?

For questions or issues, open a GitHub issue or contact the Adaptix platform team.
