# Search and Add Packages

> **Status:** Current canonical (alpha 0 grouped CLI)

Use this path when you want to discover LKM-backed knowledge and bring a paper
package into a Gaia project.

## Configure Access

```bash
gaia search lkm auth status
gaia search lkm auth login
```

You can also provide an access key through `GAIA_LKM_ACCESS_KEY` or
`LKM_ACCESS_KEY`.

## Search

```bash
gaia search lkm knowledge "falling bodies"
gaia search lkm reasoning "Mendel segregation"
gaia search lkm reasoning --claim-id <claim-id>
gaia search lkm package --paper-id <paper-id>
```

Retrieval scores are ranking signals only. Do not copy them into Gaia priors.

## Add A Paper Package

```bash
gaia pkg add --lkm-index bohrium --lkm-paper <paper-id>
gaia pkg add lkm:bohrium:paper:<paper-id>
```

`gaia pkg add` materializes the LKM paper graph under `.gaia/lkm_packages/`,
compiles it, and adds it as an editable dependency.

For a claim id, resolve the claim to its backing paper first:

```bash
gaia search lkm reasoning --claim-id <claim-id>
gaia pkg add --lkm-index bohrium --lkm-claim <claim-id>
gaia pkg add lkm:bohrium:claim:<claim-id>
```

The claim forms are recognized source refs, but they do not install standalone
claim nodes. They print the backing-paper resolution step; add the returned
paper package after inspection.

## What To Read Next

- [CLI Reference: search](../../reference/cli/search.md) for LKM search and auth commands.
- [CLI Reference: pkg](../../reference/cli/pkg.md) for `pkg add`.
