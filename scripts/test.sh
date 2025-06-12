#!/bin/bash
# Claude Conductor Test Runner Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="all"
VERBOSE=false
COVERAGE=false
WATCH=false
PARALLEL=false

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Show usage information
show_usage() {
    cat << EOF
Claude Conductor Test Runner

Usage: $0 [options]

Options:
  -t, --type TYPE        Test type: unit, integration, e2e, all (default: all)
  -v, --verbose          Verbose output
  -c, --coverage         Generate coverage report
  -w, --watch            Watch mode (re-run tests on file changes)
  -p, --parallel         Run tests in parallel
  -h, --help             Show this help message

Test Types:
  unit          - Run unit tests only
  integration   - Run integration tests only
  e2e          - Run end-to-end tests only
  all          - Run all tests (default)

Examples:
  $0 --type unit --coverage
  $0 --type integration --verbose
  $0 --watch --parallel

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -t|--type)
                TEST_TYPE="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -c|--coverage)
                COVERAGE=true
                shift
                ;;
            -w|--watch)
                WATCH=true
                shift
                ;;
            -p|--parallel)
                PARALLEL=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# Check if virtual environment is activated
check_venv() {
    if [ -z "$VIRTUAL_ENV" ]; then
        if [ -d "venv" ]; then
            print_status "Activating virtual environment..."
            source venv/bin/activate
        else
            print_error "Virtual environment not found. Run scripts/setup.sh first."
            exit 1
        fi
    fi
}

# Install test dependencies
install_test_deps() {
    print_status "Checking test dependencies..."
    
    # Check if pytest is installed
    if ! python -c "import pytest" &> /dev/null; then
        print_status "Installing pytest..."
        pip install pytest pytest-asyncio pytest-timeout pytest-mock
    fi
    
    # Install coverage tools if needed
    if [ "$COVERAGE" = true ]; then
        if ! python -c "import pytest_cov" &> /dev/null; then
            print_status "Installing coverage tools..."
            pip install pytest-cov coverage
        fi
    fi
    
    # Install watch tools if needed
    if [ "$WATCH" = true ]; then
        if ! command -v watchmedo &> /dev/null; then
            print_status "Installing watchdog..."
            pip install watchdog
        fi
    fi
    
    # Install parallel execution tools if needed
    if [ "$PARALLEL" = true ]; then
        if ! python -c "import pytest_xdist" &> /dev/null; then
            print_status "Installing pytest-xdist..."
            pip install pytest-xdist
        fi
    fi
}

# Run unit tests
run_unit_tests() {
    print_header "Running Unit Tests"
    
    local test_args=""
    
    # Build test arguments
    if [ "$VERBOSE" = true ]; then
        test_args="$test_args -v"
    fi
    
    if [ "$COVERAGE" = true ]; then
        test_args="$test_args --cov=conductor --cov-report=term-missing --cov-report=html"
    fi
    
    if [ "$PARALLEL" = true ]; then
        test_args="$test_args -n auto"
    fi
    
    # Run unit tests
    python -m pytest tests/unit/ $test_args
}

# Run integration tests
run_integration_tests() {
    print_header "Running Integration Tests"
    
    local test_args=""
    
    if [ "$VERBOSE" = true ]; then
        test_args="$test_args -v"
    fi
    
    if [ "$COVERAGE" = true ]; then
        test_args="$test_args --cov=conductor --cov-report=term-missing --cov-append"
    fi
    
    # Integration tests should not run in parallel by default
    # as they may have shared resources
    
    # Run integration tests
    python -m pytest tests/integration/ $test_args
}

# Run end-to-end tests
run_e2e_tests() {
    print_header "Running End-to-End Tests"
    
    local test_args=""
    
    if [ "$VERBOSE" = true ]; then
        test_args="$test_args -v"
    fi
    
    # E2E tests typically take longer
    test_args="$test_args --timeout=300"
    
    # Run e2e tests
    python -m pytest tests/e2e/ $test_args
}

# Run linting
run_lint() {
    print_header "Running Code Quality Checks"
    
    # Check if linting tools are available
    local lint_tools=()
    
    if command -v black &> /dev/null; then
        lint_tools+=("black")
    fi
    
    if command -v flake8 &> /dev/null; then
        lint_tools+=("flake8")
    fi
    
    if command -v mypy &> /dev/null; then
        lint_tools+=("mypy")
    fi
    
    if [ ${#lint_tools[@]} -eq 0 ]; then
        print_warning "No linting tools found. Install with: pip install black flake8 mypy"
        return
    fi
    
    # Run Black
    if [[ " ${lint_tools[@]} " =~ " black " ]]; then
        print_status "Running Black formatter check..."
        black --check conductor/ tests/ examples/ || print_warning "Black formatting issues found"
    fi
    
    # Run Flake8
    if [[ " ${lint_tools[@]} " =~ " flake8 " ]]; then
        print_status "Running Flake8 linter..."
        flake8 conductor/ tests/ examples/ || print_warning "Flake8 issues found"
    fi
    
    # Run MyPy
    if [[ " ${lint_tools[@]} " =~ " mypy " ]]; then
        print_status "Running MyPy type checker..."
        mypy conductor/ || print_warning "MyPy type issues found"
    fi
}

# Run security checks
run_security_checks() {
    print_header "Running Security Checks"
    
    if command -v bandit &> /dev/null; then
        print_status "Running Bandit security scanner..."
        bandit -r conductor/ -f json -o security-report.json || print_warning "Security issues found"
        print_status "Security report saved to security-report.json"
    else
        print_warning "Bandit not found. Install with: pip install bandit"
    fi
    
    if command -v safety &> /dev/null; then
        print_status "Running Safety dependency checker..."
        safety check || print_warning "Dependency security issues found"
    else
        print_warning "Safety not found. Install with: pip install safety"
    fi
}

# Run tests in watch mode
run_watch_mode() {
    print_header "Running Tests in Watch Mode"
    print_status "Watching for file changes... Press Ctrl+C to stop"
    
    watchmedo shell-command \
        --patterns="*.py" \
        --recursive \
        --command="$0 --type $TEST_TYPE $([ "$VERBOSE" = true ] && echo "--verbose") $([ "$COVERAGE" = true ] && echo "--coverage")" \
        conductor/ tests/
}

# Generate test report
generate_report() {
    if [ "$COVERAGE" = true ]; then
        print_header "Test Coverage Report"
        
        if [ -f ".coverage" ]; then
            coverage report
            coverage html
            print_status "HTML coverage report generated in htmlcov/"
        fi
    fi
    
    # Generate JUnit XML for CI
    if [ -n "$CI" ]; then
        print_status "Generating JUnit XML report for CI..."
        python -m pytest --junitxml=test-results.xml tests/
    fi
}

# Clean test artifacts
clean_artifacts() {
    print_status "Cleaning test artifacts..."
    
    # Remove coverage files
    rm -f .coverage
    rm -rf htmlcov/
    
    # Remove pytest cache
    rm -rf .pytest_cache/
    
    # Remove test results
    rm -f test-results.xml
    rm -f security-report.json
    
    # Remove __pycache__ directories
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    
    print_status "Test artifacts cleaned"
}

# Main test runner function
main() {
    print_header "Claude Conductor Test Runner"
    
    # Handle special commands
    case ${1:-} in
        clean)
            clean_artifacts
            exit 0
            ;;
        lint)
            check_venv
            run_lint
            exit 0
            ;;
        security)
            check_venv
            run_security_checks
            exit 0
            ;;
    esac
    
    check_venv
    install_test_deps
    
    # Handle watch mode
    if [ "$WATCH" = true ]; then
        run_watch_mode
        exit 0
    fi
    
    # Run tests based on type
    case $TEST_TYPE in
        unit)
            run_unit_tests
            ;;
        integration)
            run_integration_tests
            ;;
        e2e)
            run_e2e_tests
            ;;
        all)
            run_unit_tests
            run_integration_tests
            run_e2e_tests
            ;;
        *)
            print_error "Invalid test type: $TEST_TYPE"
            print_error "Valid types: unit, integration, e2e, all"
            exit 1
            ;;
    esac
    
    # Generate reports
    generate_report
    
    print_status "All tests completed successfully!"
}

# Handle special cases
if [ "$1" = "clean" ] || [ "$1" = "lint" ] || [ "$1" = "security" ]; then
    main "$@"
else
    parse_args "$@"
    main
fi