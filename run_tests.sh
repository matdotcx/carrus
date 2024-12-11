#!/bin/bash
# run_tests.sh

# Ensure we're in the project root
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run tests
echo "Running Carrus test suite..."
python test_suite.py $@

# Get exit code
EXIT_CODE=$?

# Print summary based on exit code
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n✨ All tests passed!"
else
    echo -e "\n❌ Some tests failed. Check the test report for details."
fi

exit $EXIT_CODE
