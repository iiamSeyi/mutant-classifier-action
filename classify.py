#!/usr/bin/env python3
"""
classify.py
===========
Phase 1: Stub classifier — parses PIT's XML output and produces a report.
The classify_mutant() function is the ONLY thing that changes in Phase 3.
Everything else (XML parsing, reporting, GitHub annotations) stays the same.

This design is intentional: build and validate the full plumbing in Phase 1,
then swap in real ML in Phase 3 without touching anything else.

Usage:
    python classify.py \\
        --pit-xml path/to/mutations.xml \\
        --output-dir path/to/output/ \\
        --confidence-threshold 0.90 \\
        --fail-below 0.70
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Mutant:
    """Represents a single mutant from PIT's XML output."""
    mutant_id: str
    source_file: str
    mutated_class: str
    mutated_method: str
    line_number: int
    mutation_operator: str   # e.g. CONDITIONALS_BOUNDARY, NEGATE_CONDITIONALS
    description: str         # human-readable description of the change
    pit_status: str          # KILLED, SURVIVED, NO_COVERAGE, TIMED_OUT
    # Fields populated by classifier:
    classifier_label: str = "UNKNOWN"     # EQUIVALENT or NON_EQUIVALENT
    classifier_confidence: float = 0.0
    classifier_note: str = ""


# ── XML Parser ────────────────────────────────────────────────────────────────

def parse_pit_xml(xml_path: str) -> list[Mutant]:
    """
    Parse PIT's mutations.xml file into a list of Mutant objects.

    PIT's XML structure looks like:
        <mutations>
            <mutation detected="true" status="KILLED" numberOfTestsRun="3">
                <sourceFile>Calculator.java</sourceFile>
                <mutatedClass>com.example.Calculator</mutatedClass>
                <mutatedMethod>add</mutatedMethod>
                <mutatedMethodDesc>(II)I</mutatedMethodDesc>
                <lineNumber>14</lineNumber>
                <mutator>org.pitest.mutationtest.engine.gregor.mutators.MathMutator</mutator>
                <index>0</index>
                <block>0</block>
                <killingTest>com.example.CalculatorTest.[engine:junit-jupiter]/...</killingTest>
                <description>Replaced integer addition with subtraction</description>
            </mutation>
            ...
        </mutations>

    We focus on SURVIVED and NO_COVERAGE mutants — these are the ones the
    classifier needs to examine. KILLED mutants are not equivalent by definition
    (a test killed them, proving behavioral difference).
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    mutants = []
    for i, mutation_elem in enumerate(root.findall('mutation')):
        status = mutation_elem.get('status', 'UNKNOWN')

        # Extract the short mutator name from the fully-qualified class name
        # e.g. "org.pitest.mutationtest...MathMutator" -> "MathMutator"
        mutator_fqn = mutation_elem.findtext('mutator', default='Unknown')
        mutator_short = mutator_fqn.split('.')[-1] if '.' in mutator_fqn else mutator_fqn

        mutant = Mutant(
            mutant_id=f"mutant_{i:04d}",
            source_file=mutation_elem.findtext('sourceFile', default='Unknown'),
            mutated_class=mutation_elem.findtext('mutatedClass', default='Unknown'),
            mutated_method=mutation_elem.findtext('mutatedMethod', default='Unknown'),
            line_number=int(mutation_elem.findtext('lineNumber', default='0')),
            mutation_operator=mutator_short,
            description=mutation_elem.findtext('description', default=''),
            pit_status=status,
        )
        mutants.append(mutant)

    return mutants


# ── Classifier ────────────────────────────────────────────────────────────────

def classify_mutant(mutant: Mutant) -> tuple[str, float, str]:
    """
    Classify a single mutant as EQUIVALENT or NON_EQUIVALENT.

    Returns:
        label       : "EQUIVALENT" or "NON_EQUIVALENT"
        confidence  : float 0.0-1.0
        note        : human-readable explanation

    ╔══════════════════════════════════════════════════════════════╗
    ║  PHASE 1 STUB                                                ║
    ║  This function always returns NON_EQUIVALENT.                ║
    ║  In Phase 3, this is replaced with:                          ║
    ║    1. AST extraction via javalang                            ║
    ║    2. Word2Vec embedding of AST tokens                       ║
    ║    3. Inference through the trained Bi-GRU / LSTM / RNN      ║
    ║  Everything outside this function stays unchanged.           ║
    ╚══════════════════════════════════════════════════════════════╝

    Why only classify SURVIVED/NO_COVERAGE mutants?
    KILLED mutants were provably caught by a test — they cannot be equivalent
    by definition. Only un-killed mutants need the classifier.
    """
    if mutant.pit_status == "KILLED":
        return "NON_EQUIVALENT", 1.0, "Killed by test suite - not equivalent"

    if mutant.pit_status == "NO_COVERAGE":
        # No test even runs this code - could be equivalent or just untested.
        # Phase 1: conservatively mark as NON_EQUIVALENT (don't discard it).
        return "NON_EQUIVALENT", 0.5, "STUB: No coverage - needs ML classification in Phase 3"

    # SURVIVED - the interesting case. A test ran but didn't catch the change.
    # This is where the ML model will do its work in Phase 3.
    return "NON_EQUIVALENT", 0.5, "STUB: Survived - needs ML classification in Phase 3"


# ── Reporting ─────────────────────────────────────────────────────────────────

def write_github_annotations(mutants: list[Mutant], threshold: float):
    """
    Emit GitHub workflow commands to annotate files in the PR diff.

    Format: ::warning file=<path>,line=<n>::<message>
    These appear as inline comments on changed files in the PR view.

    We annotate:
    - Survived mutants (test coverage gap)
    - High-confidence equivalent mutants (filtered from score)
    """
    for m in mutants:
        if m.pit_status == "SURVIVED":
            if m.classifier_label == "EQUIVALENT" and m.classifier_confidence >= threshold:
                print(f"::notice file={m.source_file},line={m.line_number}::"
                      f"[Equivalent mutant] {m.mutation_operator}: {m.description} "
                      f"(confidence: {m.classifier_confidence:.0%}) - excluded from score")
            elif m.classifier_label == "NON_EQUIVALENT":
                print(f"::warning file={m.source_file},line={m.line_number}::"
                      f"[Surviving mutant] {m.mutation_operator}: {m.description} "
                      f"- consider adding a test to kill this mutant")


def write_json_report(mutants: list[Mutant], output_dir: str,
                      raw_score: float, adjusted_score: float,
                      equiv_count: int, threshold: float):
    """Write a machine-readable JSON report for dashboards and trend tracking."""
    report = {
        "summary": {
            "total_mutants": len(mutants),
            "killed": sum(1 for m in mutants if m.pit_status == "KILLED"),
            "survived": sum(1 for m in mutants if m.pit_status == "SURVIVED"),
            "no_coverage": sum(1 for m in mutants if m.pit_status == "NO_COVERAGE"),
            "equivalent_detected": equiv_count,
            "raw_mutation_score": round(raw_score, 4),
            "adjusted_mutation_score": round(adjusted_score, 4),
            "confidence_threshold_used": threshold,
            "classifier_version": "phase1-stub",
        },
        "mutants": [asdict(m) for m in mutants],
    }

    report_path = Path(output_dir) / "mutation-report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"JSON report written: {report_path}")
    return str(report_path)


def write_results_env(output_dir: str, raw_score: float, adjusted_score: float,
                      equiv_count: int, total: int):
    """
    Write a shell-sourceable env file that entrypoint.sh reads to set
    GitHub step outputs. Key=value, one per line.
    """
    env_path = Path(output_dir) / "results.env"
    with open(env_path, "w") as f:
        f.write(f"RAW_SCORE={raw_score:.4f}\n")
        f.write(f"ADJUSTED_SCORE={adjusted_score:.4f}\n")
        f.write(f"EQUIV_COUNT={equiv_count}\n")
        f.write(f"TOTAL_MUTANTS={total}\n")
    print(f"Results env written: {env_path}")


# ── Score calculation ──────────────────────────────────────────────────────────

def calculate_scores(mutants: list[Mutant], threshold: float) -> tuple[float, float, int]:
    """
    Calculate raw and adjusted mutation scores.

    Raw score    = killed / (total - no_coverage)   [standard PIT metric]
    Adjusted     = killed / (total - no_coverage - equivalent_detected)

    The adjusted score is the key contribution of this tool: by removing
    equivalent mutants from the denominator, it gives a more accurate picture
    of how well the test suite covers real behavioral differences.
    """
    killed = sum(1 for m in mutants if m.pit_status == "KILLED")
    no_coverage = sum(1 for m in mutants if m.pit_status == "NO_COVERAGE")
    total = len(mutants)

    # Equivalent = SURVIVED mutants classified as equivalent above threshold
    equiv_count = sum(
        1 for m in mutants
        if m.pit_status == "SURVIVED"
        and m.classifier_label == "EQUIVALENT"
        and m.classifier_confidence >= threshold
    )

    denominator_raw = total - no_coverage
    raw_score = killed / denominator_raw if denominator_raw > 0 else 0.0

    denominator_adj = denominator_raw - equiv_count
    adjusted_score = killed / denominator_adj if denominator_adj > 0 else 0.0

    return raw_score, adjusted_score, equiv_count


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Equivalent Mutant Classifier")
    parser.add_argument("--pit-xml",    required=True,  help="Path to PIT mutations.xml")
    parser.add_argument("--output-dir", required=True,  help="Directory for output files")
    parser.add_argument("--confidence-threshold", type=float, default=0.90)
    parser.add_argument("--fail-below", type=float, default=0.0,
                        help="Fail if adjusted score is below this value")
    args = parser.parse_args()

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # 1. Parse PIT XML
    print(f"\nParsing PIT output: {args.pit_xml}")
    mutants = parse_pit_xml(args.pit_xml)
    print(f"  Found {len(mutants)} mutants")

    # 2. Classify each mutant
    print(f"\nClassifying mutants (threshold: {args.confidence_threshold:.0%})...")
    for mutant in mutants:
        label, confidence, note = classify_mutant(mutant)
        mutant.classifier_label = label
        mutant.classifier_confidence = confidence
        mutant.classifier_note = note

    # 3. Calculate scores
    raw_score, adjusted_score, equiv_count = calculate_scores(
        mutants, args.confidence_threshold
    )

    # 4. Print summary to CI log
    print(f"\n{'='*50}")
    print(f"  Total mutants:           {len(mutants)}")
    print(f"  Killed:                  {sum(1 for m in mutants if m.pit_status == 'KILLED')}")
    print(f"  Survived:                {sum(1 for m in mutants if m.pit_status == 'SURVIVED')}")
    print(f"  Equivalent detected:     {equiv_count}")
    print(f"  Raw mutation score:      {raw_score:.1%}")
    print(f"  Adjusted mutation score: {adjusted_score:.1%}")
    print(f"{'='*50}\n")

    # 5. Write GitHub annotations (inline PR comments)
    write_github_annotations(mutants, args.confidence_threshold)

    # 6. Write reports
    write_json_report(mutants, args.output_dir, raw_score, adjusted_score,
                      equiv_count, args.confidence_threshold)
    write_results_env(args.output_dir, raw_score, adjusted_score,
                      equiv_count, len(mutants))

    # 7. Quality gate - fail the workflow if score is too low
    if args.fail_below > 0 and adjusted_score < args.fail_below:
        print(f"::error::Adjusted mutation score {adjusted_score:.1%} is below "
              f"required threshold {args.fail_below:.1%}. Improve test coverage.")
        sys.exit(1)

    print("Classifier completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()