#!/usr/bin/env python3
"""Fail-closed verifier for an externally produced Platform V1 release dossier.

Run on the release rehearsal host, with sibling checkouts of all seven repositories.
The attestation is intentionally outside Git: this repository cannot contain its
own final commit hash or the digest of an image that has not been built yet.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT.parent
REPOS = (
    "vox-core", "vox-web", "vox-bridge", "agents", "vox-deploy",
    "feno-extension", "vox-contracts",
)
IMAGES = ("core-api", "core-worker", "bridge", "vox-web", "portable-agent", "conformance-sandbox")
SERVICES = (*IMAGES, "postgres", "redis")
GATES = (
    "traceability",
    "product-real-core",
    "security-and-privacy",
    "independent-host",
    "provider-connected-read",
    "provider-approved-write",
    "transaction-sandbox",
    "remote-extension",
    "clean-install",
    "upgrade-and-rollback",
    "backup-and-restore",
    "accessibility-and-usability",
    "license-and-legal",
    "single-user-latency",
)
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r".+@sha256:[0-9a-f]{64}\Z")


def fail(message: str) -> None:
    raise ValueError(message)


def command(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def verify() -> None:
    evidence_path = Path(os.environ.get("VOX_RELEASE_EVIDENCE", ""))
    if not evidence_path.is_file():
        fail("VOX_RELEASE_EVIDENCE must name a real release attestation JSON file")
    evidence = json.loads(evidence_path.read_text())
    manifest = json.loads((ROOT / "deployments/manifest.json").read_text())
    if manifest.get("release_status") != "pending_evidence":
        fail("source manifest must remain a candidate, not assert a release")

    commits = evidence.get("source_commits", {})
    for repo in REPOS:
        expected = commits.get(repo)
        if not isinstance(expected, str) or not SHA.fullmatch(expected):
            fail(f"missing exact source commit for {repo}")
        checkout = SUITE / repo
        if command("git", "rev-parse", "HEAD", cwd=checkout) != expected:
            fail(f"checkout does not match attested {repo} commit")
        if command("git", "status", "--porcelain", cwd=checkout):
            fail(f"{repo} checkout has uncommitted changes")
        pinned = manifest["repositories"][repo].get("commit")
        if repo != "vox-deploy" and pinned != expected:
            fail(f"source manifest does not match {repo} commit")

    images = evidence.get("images", {})
    for service in IMAGES:
        image = images.get(service)
        if not isinstance(image, str) or not DIGEST.fullmatch(image):
            fail(f"missing digest-pinned image for {service}")
        inspect = json.loads(command("docker", "image", "inspect", image))
        if not inspect or image not in inspect[0].get("RepoDigests", []):
            fail(f"image digest is not present locally: {service}")

    configured = json.loads(command("docker", "compose", "-f", "compose.self-hosted.yml", "config", "--format", "json"))
    for service in SERVICES:
        actual = configured.get("services", {}).get(service, {}).get("image")
        if service in IMAGES and actual != images[service]:
            fail(f"running Compose configuration does not pin {service} to attested image")
    running = set(command("docker", "compose", "-f", "compose.self-hosted.yml", "ps", "--status", "running", "--services").splitlines())
    if missing := set(SERVICES) - running:
        fail(f"release stack is not running: {', '.join(sorted(missing))}")

    gates = evidence.get("gates", {})
    for gate in GATES:
        record = gates.get(gate, {})
        if record.get("result") != "pass" or not record.get("command") or not record.get("recorded_at"):
            fail(f"missing passing evidence record for {gate}")
        log = evidence_path.parent / record.get("log", "")
        if not log.is_file() or log == evidence_path:
            fail(f"missing evidence log for {gate}")
        digest = hashlib.sha256(log.read_bytes()).hexdigest()
        if digest != record.get("sha256"):
            fail(f"evidence log digest mismatch for {gate}")

    latency_run = evidence_path.parent / gates["single-user-latency"].get("run_json", "")
    if not latency_run.is_file():
        fail("single-user latency gate lacks its measured run JSON")
    command(sys.executable, "scripts/check-single-user-latency.py", str(latency_run))

    prd = (SUITE / "vox-contracts/docs/PRD.md").read_text()
    required = set(re.findall(r"\bFR-[A-Z]+-\d{3} \(P0\)", prd))
    required = {item.split(" ", 1)[0] for item in required}
    required.update(re.findall(r"\bNFR-[A-Z]+-\d{3}\b", prd))
    required.update(re.findall(r"^### (AS-\d{3}):", prd, re.MULTILINE))
    required.update(f"RELEASE-19.{number}" for number in range(1, 7))
    requirements = evidence.get("requirements", {})
    if missing := required - requirements.keys():
        fail(f"traceability lacks {len(missing)} required items, starting with {sorted(missing)[0]}")
    for requirement in required:
        record = requirements[requirement]
        if record.get("result") != "pass" or record.get("gate") not in GATES or not record.get("assertion"):
            fail(f"requirement has no passing assertion and evidence gate: {requirement}")

    print("Platform V1 evidence dossier verified; human and provider claims remain subject to review.")


if __name__ == "__main__":
    try:
        verify()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"Platform V1 release blocked: {error}", file=sys.stderr)
        sys.exit(1)
