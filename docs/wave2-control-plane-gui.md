# Wave 2 — Control Plane GUI

Adds a read-only Control Plane workspace to the existing local GUI.

The browser consumes `GET /api/control-plane` only. There is deliberately no control-plane POST endpoint.

Displayed domains:
- workflows / tasks / job attempts;
- specialists and methodology/model/authority bindings;
- model profiles and loaded runtime resources;
- artifacts and validation/promotion state;
- verification/resource events.

The view reads the existing authoritative `DATA_ROOT/control-plane.db`; it does not create a second state store or execution authority.
