# Gaia Documentation

This directory mixes three different kinds of material:

1. Current architecture and repo navigation
2. Design and theory notes
3. Historical planning documents from the initial build-out

The main source of confusion in the current docs is that those categories are not clearly separated. Start with the files below.

## Start Here

- [Module Map](module-map.md): current repo structure, module boundaries, and known areas that still need cleanup
- [Repository README](../README.md): quick start, runtime overview, and API entry points

## Documentation Map

### Current structure

- [Module Map](module-map.md): current top-level directories, service boundaries, and dependency flow
- [Architecture Re-baseline](architecture-rebaseline.md): current structural problems and the recommended cleanup path
- [Foundations](foundations/README.md): foundation-first planning area for architecture, schema, module, and API reset work

### Design references

- [Theoretical Foundations](design/theoretical_foundations.md): belief graph model and reasoning semantics
- [Scaling Belief Propagation](design/scaling_belief_propagation.md): scaling ideas for inference
- [Billion-Scale Phase 1](design/phase1_billion_scale.md): system-level design direction
- [Related Work](design/related_work.md): external context

### Examples

- [Einstein Elevator](examples/einstein_elevator.md)
- [Galileo Tied Balls](examples/galileo_tied_balls.md)

### Historical plans

- [Plans README](plans/README.md): archived implementation plans, API drafts, and execution notes

`docs/plans/` is useful for understanding why the code looks the way it does, but it should not be treated as the current architecture spec.
