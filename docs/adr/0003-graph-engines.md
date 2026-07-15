# ADR 0003: Graph Engines

- **Status:** Accepted
- **Date:** 2026-07-15
- **Deciders:** Product roadmap / Phase 0

## Context

BrainFlow needs editable workflow DAGs, trees, and mind maps, plus dense knowledge/relationship exploration, all projecting one canonical graph model. A single rendering library is unlikely to excel at both authoring UX and large exploratory graphs.

## Decision

- **React Flow + ELK (Web Worker)** for editable workflow DAGs, trees, and mind maps.  
- **Cytoscape.js** for dense relationship / knowledge exploration.  
- Both consume projections from the same canonical typed graph ([GRAPH_MODEL.md](../GRAPH_MODEL.md)).  
- Mandatory synchronized non-visual outline/list/table for accessibility.

## Consequences

**Positive:** Fit-for-purpose UX per view; shared semantic model avoids divergent diagrams.  
**Negative:** Two UI dependencies; must invest in projection sync and a11y twins.  
**Follow-up:** React Flow + ELK worker and Cytoscape LOD landed ([../spikes/graph-scale.md](../spikes/graph-scale.md)); mid-tier 500-node UI soak and full keyboard/AT sign-off remain open.
