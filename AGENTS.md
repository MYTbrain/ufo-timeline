## Mandatory storage-lifecycle policy

This is a data-heavy project and C: storage is constrained.

1. Protected by default: raw inputs, source archives, canonical datasets, manifests,
   provenance, unique analyses, databases, coordinate corrections, current runtime
   assets, unpushed Git work, the current validated release, and one known-good
   rollback release.

2. Never create a complete copy of any file or directory expected to exceed 1 GiB
   without explicit user approval. Prefer shared canonical data, manifests, hashes,
   deltas, and reproducible transformations.

3. Do not create timestamped full copies of canonical datasets, static bundles,
   repositories, or staging trees merely as a rollback mechanism.

4. Retain exactly one current validated deployment and one last-known-good rollback
   unless the user explicitly authorizes additional retained releases.

5. Worktrees must reference shared canonical datasets. Do not copy the complete UFO
   corpus, complete static bundle, or complete analysis database into each worktree.

6. Worktree setup scripts must not generate the full catalog, build the complete
   static bundle, copy source datasets, or reproduce historical releases unless the
   current task explicitly requires that operation.

7. Before creating any artifact expected to exceed 1 GiB, report:
   - destination path;
   - expected size;
   - whether an equivalent artifact already exists;
   - why the artifact is necessary;
   - how and when it will be cleaned up.

8. After every successful build, analysis, ingestion, or deployment:
   - designate the new canonical artifact;
   - designate the retained rollback;
   - identify superseded staging and backup artifacts;
   - list newly created files larger than 100 MiB;
   - report approximate net disk-space growth;
   - propose cleanup of superseded generated artifacts.

9. Temporary, staging, reproduction, recovery, pre-apply, backup, old, final, and
   versioned directories must have a documented purpose, provenance, rebuild method,
   and retention decision. No task may finish with an unexplained large directory.

10. Dataset or analysis deletion requires an explicit allowlist with literal paths,
    sizes, hashes when practical, evidence of redundancy or reproducibility, and the
    retained canonical counterpart. Never use wildcard or broad recursive deletion.

11. While C: has less than 100 GiB free, do not perform a net-positive operation
    expected to add more than 100 MiB to C: without explicit user approval. After C:
    exceeds 100 GiB free, maintain at least that reserve when planning large tasks.

12. D: is the primary local safety-backup and quarantine location. E: may be used
    only as a secondary redundant copy and must never hold the sole surviving copy
    of necessary project data.
