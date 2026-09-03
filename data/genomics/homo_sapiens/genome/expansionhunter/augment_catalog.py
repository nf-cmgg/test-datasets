"""Augment ExpansionHunter catalog with the fields Stranger needs.

This does NOT build a new catalog. It takes the original catalog already containing genotypes and adds pathogenicity thresholds from STRchive, so that one file can be
passed to both tools:

    expansionhunter --variant-catalog <output>
    stranger --repeats-file <output>

Guarantees, enforced by assertions before anything is written:
  * every input locus appears in the output (no locus is ever dropped)
  * LocusId, LocusStructure and ReferenceRegion are byte-identical to the input

Those three fields define what ExpansionHunter genotypes. Changing them is a
clinical change; adding annotation fields is not.

Matching is by genomic position, not gene name. Name matching does not resolve for all loci in some cases.

Usage:
    python augment_catalog.py \
        --catalog variant_catalog_illumina_hg38_original.json \
        --strchive STRchive-loci.json \
        --output variant_catalog_hg38_illumina.json
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

# Overlap slack when matching a catalog region to a STRchive locus. The two
# sources disagree by up to ~100bp on where a repeat starts/stops.
POSITION_TOLERANCE = 200

# Optional fields Stranger copies straight into the VCF INFO. Keys must match
# stranger/constants.py:ANNOTATE_REPEAT_KEYS exactly -- note "HGNCId", not
# "HGNC_ID" as the README suggests.
ANNOTATION_FIELDS = ["Disease", "InheritanceMode", "DisplayRU", "Source", "SourceId"]


# --------------------------------------------------------------------------
# parsing helpers
# --------------------------------------------------------------------------

def regions_of(locus):
    """Yield (chrom, start, stop) for a catalog locus.

    ReferenceRegion is a string for most loci but a list for compound ones
    (ATXN7, ATXN8OS, CNBP, FXN, HTT, NOP56). Both shapes must work.
    """
    region = locus["ReferenceRegion"]
    for item in region if isinstance(region, list) else [region]:
        chrom, span = item.split(":")
        start, stop = span.split("-")
        yield chrom.replace("chr", ""), int(start), int(stop)


def is_compound(locus):
    return isinstance(locus["ReferenceRegion"], list)


def index_strchive(strchive):
    """Bucket STRchive loci by chromosome for a cheap overlap lookup."""
    by_chrom = defaultdict(list)
    for entry in strchive:
        if entry.get("start_hg38") is None or entry.get("stop_hg38") is None:
            continue
        chrom = (entry.get("chrom") or "").replace("chr", "")
        by_chrom[chrom].append(entry)
    return by_chrom


def find_matches(locus, by_chrom):
    """All STRchive entries overlapping any region of this locus."""
    hits = []
    for chrom, start, stop in regions_of(locus):
        for entry in by_chrom.get(chrom, []):
            if entry["stop_hg38"] < start - POSITION_TOLERANCE:
                continue
            if entry["start_hg38"] > stop + POSITION_TOLERANCE:
                continue
            if entry not in hits:
                hits.append(entry)
    return hits


# --------------------------------------------------------------------------
# side files (biology decisions, kept out of the code so they can be reviewed)
# --------------------------------------------------------------------------

def load_side_file(path, description):
    if path is None:
        return {}
    try:
        with open(path) as handle:
            return json.load(handle)
    except FileNotFoundError:
        sys.exit(
            f"ERROR: {description} not found at {path}.\n"
            f"       Re-run with --write-templates to generate a starting point."
        )


def write_templates(catalog, by_chrom, regions_path, overrides_path):
    """Emit fill-in-the-blank side files for the decisions a human must make."""
    compound = {}
    for locus in catalog:
        if is_compound(locus):
            compound[locus["LocusId"]] = {
                "_available_regions": locus["ReferenceRegion"],
                "PathologicRegion": None,  # <- fill in: which region carries the expansion
            }

    ambiguous = {}
    for locus in catalog:
        hits = find_matches(locus, by_chrom)
        if len(hits) > 1:
            ambiguous[locus["LocusId"]] = {
                "_candidates": [h.get("disease_id") for h in hits],
                "disease_id": None,  # <- fill in: which STRchive entry to use
            }

    with open(regions_path, "w") as handle:
        json.dump(compound, handle, indent=2)
    with open(overrides_path, "w") as handle:
        json.dump(ambiguous, handle, indent=2)

    print(f"Wrote {regions_path} ({len(compound)} compound loci need PathologicRegion)")
    print(f"Wrote {overrides_path} ({len(ambiguous)} loci match multiple STRchive entries)")
    print("\nFill in the null values, then re-run without --write-templates.")


# --------------------------------------------------------------------------
# the augmentation itself
# --------------------------------------------------------------------------

def annotation_from(entry):
    """Map STRchive fields onto Stranger's optional annotation keys."""
    fields = {}
    if entry.get("disease"):
        # the human-readable name, not disease_id -- this ends up in a report
        fields["Disease"] = entry["disease"]
    if entry.get("inheritance"):
        fields["InheritanceMode"] = entry["inheritance"][0]
    motifs = entry.get("reference_motif_reference_orientation")
    if motifs:
        fields["DisplayRU"] = motifs[0]
    fields["Source"] = "STRchive"
    if entry.get("disease_id"):
        fields["SourceId"] = entry["disease_id"]
    return fields


def augment(catalog, strchive, pathologic_regions, overrides, normalmax_fallback):
    by_chrom = index_strchive(strchive)
    report = {"annotated": [], "no_match": [], "no_thresholds": [],
              "derived_normalmax": [], "ambiguous": [], "missing_region": []}

    for locus in catalog:
        locus_id = locus["LocusId"]

        # --- PathologicRegion: without it Stranger silently skips compound loci
        if is_compound(locus):
            chosen = (pathologic_regions.get(locus_id) or {}).get("PathologicRegion")
            if chosen:
                locus["PathologicRegion"] = chosen
            else:
                report["missing_region"].append(locus_id)

        # --- find the STRchive entry
        hits = find_matches(locus, by_chrom)
        if not hits:
            report["no_match"].append(locus_id)
            continue

        if len(hits) > 1:
            wanted = (overrides.get(locus_id) or {}).get("disease_id")
            picked = next((h for h in hits if h.get("disease_id") == wanted), None)
            if picked is None:
                report["ambiguous"].append(
                    (locus_id, [h.get("disease_id") for h in hits]))
                continue
            entry = picked
        else:
            entry = hits[0]

        # --- thresholds
        pathologic_min = entry.get("pathogenic_min")
        normal_max = entry.get("benign_max")

        if normal_max is None and normalmax_fallback:
            # STRchive has no benign_max for the FAME loci (SAMD12, STARD7,
            # MARCHF6, YEATS2, TNRC6A, RAPGEF2) or BEAN1 -- and no
            # intermediate_min either, so the first fallback rarely fires.
            # Falling back to pathogenic_min - 1 collapses the pre_mutation
            # band: every allele below the pathogenic threshold is then called
            # normal. That is a clinical judgement, which is why this is
            # opt-in and every use is logged.
            if entry.get("intermediate_min") is not None:
                normal_max = entry["intermediate_min"] - 1
                basis = "intermediate_min - 1"
            elif pathologic_min is not None:
                normal_max = pathologic_min - 1
                basis = "pathogenic_min - 1 (NO pre_mutation band)"
            if normal_max is not None:
                report["derived_normalmax"].append((locus_id, normal_max, basis))

        if pathologic_min is None or normal_max is None:
            # Locus stays in the catalog and is still genotyped -- it just
            # will not be annotated. Never drop it.
            report["no_thresholds"].append(locus_id)
            continue

        if pathologic_min <= normal_max:
            report["no_thresholds"].append(f"{locus_id} (PathologicMin <= NormalMax)")
            continue

        locus["NormalMax"] = normal_max
        locus["PathologicMin"] = pathologic_min
        locus.update(annotation_from(entry))
        report["annotated"].append(locus_id)

    return report


# --------------------------------------------------------------------------
# validation -- run before writing anything
# --------------------------------------------------------------------------

def validate(original, augmented):
    """The genotyping definition must be untouched. Fail loudly if it is not."""
    problems = []

    if len(original) != len(augmented):
        problems.append(f"locus count changed: {len(original)} -> {len(augmented)}")

    for before, after in zip(original, augmented):
        # VariantId/VariantType are part of the genotyping definition too:
        # ExpansionHunter emits one VCF record per VariantId on compound loci.
        for field in ("LocusId", "LocusStructure", "ReferenceRegion",
                      "VariantId", "VariantType", "OfftargetRegions"):
            if before.get(field) != after.get(field):
                problems.append(
                    f"{before.get('LocusId')}: {field} was modified "
                    f"({before.get(field)!r} -> {after.get(field)!r})")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalog", default="variant_catalog_illumina_hg38_original.json",
                        help="the ExpansionHunter catalog to augment")
    parser.add_argument("--strchive", default="STRchive-loci.json",
                        help="STRchive loci export (threshold source)")
    parser.add_argument("--output", default="variant_catalog_hg38_illumina.json")
    parser.add_argument("--pathologic-regions", default="pathologic_regions.json",
                        help="which region carries the expansion, for compound loci")
    parser.add_argument("--overrides", default="strchive_overrides.json",
                        help="tie-breaks for loci matching several STRchive entries")
    parser.add_argument("--write-templates", action="store_true",
                        help="generate the two side files and exit")
    parser.add_argument("--derive-normalmax", action="store_true",
                        help="when STRchive has no benign_max, use intermediate_min - 1. "
                             "Off by default: this is a clinical decision.")
    args = parser.parse_args()

    with open(args.catalog) as handle:
        catalog = json.load(handle)
    with open(args.strchive) as handle:
        strchive = json.load(handle)

    print(f"{len(catalog)} loci in {args.catalog}")
    print(f"{len(strchive)} loci in {args.strchive}\n")

    if args.write_templates:
        write_templates(catalog, index_strchive(strchive),
                        args.pathologic_regions, args.overrides)
        return 0

    original = json.loads(json.dumps(catalog))  # deep copy for the comparison

    report = augment(
        catalog,
        strchive,
        load_side_file(args.pathologic_regions, "pathologic regions file"),
        load_side_file(args.overrides, "overrides file"),
        args.derive_normalmax,
    )

    # ---- summary
    print(f"annotated            : {len(report['annotated'])}/{len(catalog)}")
    for key, label in [("no_match", "no STRchive match"),
                       ("no_thresholds", "matched, no usable thresholds"),
                       ("ambiguous", "several STRchive matches, no override")]:
        if report[key]:
            print(f"{label:21s}: {len(report[key])}")
            for item in report[key]:
                print(f"    {item}")
    if report["derived_normalmax"]:
        print(f"{'derived NormalMax':21s}: {len(report['derived_normalmax'])}")
        for locus_id, value, basis in report["derived_normalmax"]:
            print(f"    {locus_id} -> NormalMax={value} (from {basis})")
    if report["missing_region"]:
        print(f"\nWARNING: {len(report['missing_region'])} compound loci have no "
              f"PathologicRegion. Stranger WILL SKIP these:")
        for locus_id in report["missing_region"]:
            print(f"    {locus_id}")

    # ---- validation gate
    problems = validate(original, catalog)
    if problems:
        print("\nVALIDATION FAILED - nothing written:", file=sys.stderr)
        for problem in problems:
            print(f"    {problem}", file=sys.stderr)
        return 1

    # ---- provenance, so a report can be traced back to a catalog version
    with open(args.catalog, "rb") as handle:
        source_digest = hashlib.sha256(handle.read()).hexdigest()[:16]
    meta = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_catalog": args.catalog,
        "base_catalog_sha256_16": source_digest,
        "threshold_source": args.strchive,
        "loci": len(catalog),
        "annotated": len(report["annotated"]),
        "normalmax_derived": args.derive_normalmax,
    }

    with open(args.output, "w") as handle:
        json.dump(catalog, handle, indent=2)
    with open(args.output + ".meta.json", "w") as handle:
        json.dump(meta, handle, indent=2)

    print(f"\nvalidation passed - {len(catalog)} loci, genotyping definition unchanged")
    print(f"wrote {args.output}")
    print(f"wrote {args.output}.meta.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())