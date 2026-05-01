# Equivalent Mutant Classifier — GitHub Action

A GitHub Action that runs [PIT](https://pitest.org/) mutation testing on Java/Maven
projects and uses ML classification to automatically filter out equivalent mutants,
producing an **adjusted mutation score** that is more accurate than the raw PIT score.

Based on: *"Enhancing Mutation Testing Efficiency: A Comparative Study of Machine
Learning Models for Equivalent Mutant Identification"* — Pugh et al., Towson University, 2025.

---

## Project Status

### Phase 1 — COMPLETE

Full CI/CD plumbing is in place and tested end-to-end:

- PIT mutation testing runs inside a Docker container (Java 17 + Maven + Python 3.11)
- `classify.py` parses PIT XML, classifies all mutants (stub), calculates raw and adjusted
  scores, emits GitHub PR annotations, writes a JSON report, and enforces a quality gate
- `entrypoint.sh` orchestrates the full pipeline (test → PIT → classify → publish)
- `action.yml` defines 5 inputs and 5 outputs consumed by downstream workflow steps
- The CI workflow (`mutation-ci.yml`) self-tests the action on every push to `main`
- GitHub Step Summary displays a Markdown results table in the Actions UI

### Current PIT Results (sample-java-project)

| Metric                      | Value          |
|-----------------------------|----------------|
| Total mutants generated     | 36             |
| Killed                      | 31             |
| Survived                    | 5              |
| Timed out (counts as killed)| 1              |
| Raw mutation score          | **86%**        |
| Equivalent mutants detected | 0 (Phase 1 stub) |
| Adjusted mutation score     | 86% (same as raw until Phase 3) |

#### Surviving mutants breakdown

| Method      | Line | Mutator                             | Why it survives                          |
|-------------|------|-------------------------------------|------------------------------------------|
| `max()`     | 25   | ConditionalsBoundaryMutator (`>=` → `>`) | `testMax()` tests `max(4,4)` — equal inputs make `>=` and `>` identical |
| `abs()`     | 39   | ConditionalsBoundaryMutator (`<` → `<=`) | `testAbs()` tests `abs(0)=0` but doesn't distinguish `< 0` vs `<= 0` |
| `clamp()`   | 33   | ConditionalsBoundaryMutator (`<` → `<=`) | No test with `value == min` boundary     |
| `clamp()`   | 34   | ConditionalsBoundaryMutator (`>` → `>=`) | No test with `value == max` boundary     |
| `factorial()`| 44  | RemoveConditionalMutator_EQUAL_ELSE  | The `n==0` base case needs a sharper test |

---

## Repository Structure

```
mutant-classifier-action/
├── action.yml                           # GitHub Action metadata + inputs/outputs
├── Dockerfile                           # Multi-stage: Java 17 + Maven + Python 3.11
├── entrypoint.sh                        # Pipeline: mvn test → mvn pitest → classify.py → publish
├── classify.py                          # Classifier (Phase 1 stub; ML swapped in during Phase 3)
├── requirements.txt                     # lxml==5.1.0, rich==13.7.0 (Phase 3 adds torch/gensim/javalang)
├── docs/
│   ├── system-architecture.drawio       # Full system diagram (open in draw.io)
│   └── presentation-content.txt        # PPTX slide content (12 slides)
├── sample-java-project/                 # Test target — the action runs against this
│   ├── pom.xml                          # Maven build with PIT plugin configured
│   └── src/
│       ├── main/java/com/example/Calculator.java       # 9 methods
│       └── test/java/com/example/CalculatorTest.java  # 11 test methods
└── .github/workflows/
    └── mutation-ci.yml                  # CI: self-tests the action on push to main
```

---

## How to Use This Action in Another Project

Once published, add this to the target project's `.github/workflows/mutation-ci.yml`:

```yaml
name: Mutation Testing

on:
  pull_request:
    branches: [ main ]
    paths: [ 'src/**/*.java', 'pom.xml' ]

permissions:
  contents: read
  pull-requests: write

jobs:
  mutation-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run mutation testing
        id: classifier
        uses: your-org/mutant-classifier-action@v1
        with:
          confidence-threshold: '0.90'
          fail-below-score: '0.70'

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: mutation-report
          path: target/mutant-classifier-report/
```

---

## Inputs

| Input                  | Description                                                         | Default |
|------------------------|---------------------------------------------------------------------|---------|
| `working-directory`    | Path to Maven project root (where pom.xml lives)                    | `.`     |
| `confidence-threshold` | Min ML confidence (0.0–1.0) to classify a mutant as equivalent      | `0.90`  |
| `fail-below-score`     | Fail workflow if adjusted score drops below this value              | `0.0`   |
| `maven-args`           | Extra arguments passed to `mvn pitest:mutationCoverage`             | `''`    |
| `upload-report`        | Upload HTML + JSON report as workflow artifact                      | `true`  |

## Outputs

| Output                     | Description                                            |
|----------------------------|--------------------------------------------------------|
| `raw-mutation-score`       | PIT score before equivalent mutant filtering (0.0–1.0) |
| `adjusted-mutation-score`  | Score after equivalent mutants removed (0.0–1.0)       |
| `equivalent-mutants-found` | Count of mutants classified as equivalent and removed  |
| `total-mutants`            | Total mutants generated by PIT                         |
| `report-path`              | Path to the generated JSON report inside the container |

---

## classify.py Design

The classifier is intentionally split so that only one function changes between phases:

```
parse_pit_xml()             # parses mutations.xml → list[Mutant]  ← UNCHANGED
classify_mutant(mutant)     # PHASE 1: stub  |  PHASE 3: ML model  ← ONLY THING THAT CHANGES
calculate_scores()          # raw and adjusted score math           ← UNCHANGED
write_github_annotations()  # ::warning / ::notice PR comments      ← UNCHANGED
write_json_report()         # mutation-report.json                  ← UNCHANGED
write_results_env()         # results.env sourced by entrypoint.sh  ← UNCHANGED
```

### Score formulas

```
Raw score      = killed / (total - no_coverage)
Adjusted score = killed / (total - no_coverage - equivalent_detected)
```

---

## Development Phases

### Phase 1 — COMPLETE
- Full Docker container build (Java 17 + Maven + Python 3.11)
- PIT XML parsing into typed `Mutant` dataclasses
- Stub classifier (always returns NON_EQUIVALENT)
- Raw and adjusted score calculation
- GitHub PR inline annotations (::warning, ::notice)
- JSON report for dashboards and trend tracking
- Shell-sourceable `results.env` for `GITHUB_OUTPUT`
- `GITHUB_STEP_SUMMARY` Markdown table
- Quality gate: `sys.exit(1)` if adjusted score < `fail-below` threshold
- CI self-test workflow (`mutation-ci.yml`) runs on every push to `main`

### Phase 2 — UPCOMING
- Java AST feature extraction pipeline using `javalang`
- Word2Vec training on Java source corpus
- Dataset collection: labeled equivalent/non-equivalent mutants

### Phase 3 — UPCOMING
- Bi-GRU / LSTM / RNN model training
- Inference inside `classify_mutant()` (the only code change)
- `requirements.txt` additions: `torch`, `gensim`, `javalang`
- Expected: ~94% F1-score on equivalent mutant detection

---

## Immediate Next Steps

1. **Kill the 5 surviving mutants** — try Eclipse IDE for smarter test generation

   Specific tests that should kill each survivor:
   ```java
   // max() ConditionalsBoundary — add a strictly-less-than test case
   assertEquals(3, calc.max(3, 4));

   // abs() ConditionalsBoundary — test the boundary at n = -1
   assertEquals(1, calc.abs(-1));

   // clamp() ConditionalsBoundary — test value exactly at boundaries
   assertEquals(1,  calc.clamp(1,  1, 10));   // value == min
   assertEquals(10, calc.clamp(10, 1, 10));   // value == max
   ```

2. **Improve from 86% to 97%+** — once survivors are killed

3. **Begin Phase 2** — AST extraction and Word2Vec embedding pipeline

---

## Sample PIT Mutator Breakdown (current run)

| Mutator                              | Generated | Killed | Survived |
|--------------------------------------|-----------|--------|----------|
| ConditionalsBoundaryMutator          | 6         | 2      | 4        |
| RemoveConditionalMutator_EQUAL_ELSE  | 3         | 2      | 1        |
| MathMutator                          | 5         | 5      | 0        |
| PrimitiveReturnsMutator              | 11        | 11     | 0        |
| RemoveConditionalMutator_ORDER_ELSE  | 5         | 5      | 0        |
| InvertNegsMutator                    | 1         | 1      | 0        |
| IncrementsMutator                    | 1         | 1      | 0        |
| BooleanTrueReturnValsMutator         | 1         | 1      | 0        |
| BooleanFalseReturnValsMutator        | 1         | 1      | 0        |

*Plus 1 TIMED_OUT mutant (RemoveConditionalMutator_ORDER_ELSE in `factorial` loop — infinite loop if boundary removed).*

---

## References

- [PIT Mutation Testing](https://pitest.org/)
- [GitHub Actions Docker container actions](https://docs.github.com/en/actions/creating-actions/creating-a-docker-container-action)
- Pugh et al., "Enhancing Mutation Testing Efficiency: A Comparative Study of Machine Learning Models for Equivalent Mutant Identification," Towson University, 2025
