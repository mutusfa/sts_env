# STS environment — common workflows
# Run `just` to see available recipes.

# Build the sts_lightspeed oracle module (first-time setup / after submodule update)
oracle:
    ./scripts/build_oracle.sh

# Run tests (fast, no build)
test:
    python -m pytest tests/ -q

# Build oracle then run all tests
check: oracle test

# Run tests with verbose output
test-v:
    python -m pytest tests/ -v

# Run a specific test file or pattern
# Usage: just run tests/test_deck.py
run *ARGS:
    python -m pytest {{ARGS}}
