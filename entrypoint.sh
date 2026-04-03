#!/bin/bash
set -euo pipefail

# Unset JAVA_HOME injected by the GitHub Actions runner — it points to the
# runner's JDK path which doesn't exist inside this container. The container
# has its own JDK from the eclipse-temurin base image, which Maven will find
# automatically via PATH without needing JAVA_HOME set.
unset JAVA_HOME
unset JAVA_HOME_17_X64

PROJECT_DIR="${GITHUB_WORKSPACE}/${WORKING_DIR:-.}"

echo "::group::Setup"
echo "Target project: ${PROJECT_DIR}"
echo "Confidence threshold: ${CONFIDENCE_THRESHOLD}"
echo "Fail below score: ${FAIL_BELOW_SCORE}"
echo "::endgroup::"

if [ ! -f "${PROJECT_DIR}/pom.xml" ]; then
    echo "::error::No pom.xml found at ${PROJECT_DIR}. Check the working-directory input."
    exit 1
fi

cd "${PROJECT_DIR}"

echo "::group::Running unit tests"
if ! mvn test --no-transfer-progress -q; then
    echo "::error::Unit tests failed. Fix failing tests before running mutation analysis."
    exit 1
fi
echo "Unit tests passed."
echo "::endgroup::"

echo "::group::Running PIT mutation testing"
echo "This may take several minutes depending on project size..."

mvn org.pitest:pitest-maven:mutationCoverage \
    --no-transfer-progress \
    ${MAVEN_ARGS:-} \
    || {
        echo "::error::PIT mutation testing failed. Check the logs above."
        exit 1
    }
echo "::endgroup::"

PIT_REPORT_DIR="${PROJECT_DIR}/target/pit-reports"
PIT_XML="${PIT_REPORT_DIR}/mutations.xml"

if [ ! -f "${PIT_XML}" ]; then
    echo "::error::PIT XML report not found at ${PIT_XML}."
    exit 1
fi

echo "PIT report found: ${PIT_XML}"

echo "::group::Running equivalent mutant classifier"

REPORT_OUTPUT_DIR="${PROJECT_DIR}/target/mutant-classifier-report"
mkdir -p "${REPORT_OUTPUT_DIR}"

python3 /action/classify.py \
    --pit-xml "${PIT_XML}" \
    --output-dir "${REPORT_OUTPUT_DIR}" \
    --confidence-threshold "${CONFIDENCE_THRESHOLD}" \
    --fail-below "${FAIL_BELOW_SCORE}"

CLASSIFIER_EXIT=$?
echo "::endgroup::"

RESULTS_ENV="${REPORT_OUTPUT_DIR}/results.env"

if [ -f "${RESULTS_ENV}" ]; then
    source "${RESULTS_ENV}"

    {
        echo "raw-mutation-score=${RAW_SCORE:-0}"
        echo "adjusted-mutation-score=${ADJUSTED_SCORE:-0}"
        echo "equivalent-mutants-found=${EQUIV_COUNT:-0}"
        echo "total-mutants=${TOTAL_MUTANTS:-0}"
        echo "report-path=${REPORT_OUTPUT_DIR}"
    } >> "${GITHUB_OUTPUT}"

    {
        echo "## Mutation Testing Results"
        echo ""
        echo "| Metric | Value |"
        echo "|--------|-------|"
        echo "| Total mutants generated | ${TOTAL_MUTANTS:-N/A} |"
        echo "| Equivalent mutants detected | ${EQUIV_COUNT:-N/A} |"
        echo "| Raw mutation score | ${RAW_SCORE:-N/A} |"
        echo "| **Adjusted mutation score** | **${ADJUSTED_SCORE:-N/A}** |"
        echo ""
        echo "> See the full report artifact for details on each flagged mutant."
    } >> "${GITHUB_STEP_SUMMARY}"
fi

exit ${CLASSIFIER_EXIT}